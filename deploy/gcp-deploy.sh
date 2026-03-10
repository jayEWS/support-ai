#!/bin/bash
# GCP VM Deployment Script for Enterprise AI Platform
# Supports Ubuntu 20.04+ / Debian-based systems

set -e

echo "🚀 Starting Enterprise AI Platform deployment on GCP VM..."

# Configuration
PROJECT_NAME="support-ai"
REPO_URL="https://github.com/jayEWS/support-edgeworks.git"
BRANCH="main"
INSTALL_DIR="/opt/$PROJECT_NAME"
SERVICE_USER="aiplatform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root for security reasons."
   log_info "Please run as a regular user with sudo privileges."
   exit 1
fi

# Function to check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Ubuntu/Debian
    if ! command -v apt-get &> /dev/null; then
        log_error "This script requires Ubuntu/Debian (apt-get not found)"
        exit 1
    fi
    
    # Check available memory (minimum 4GB)
    available_mem=$(free -g | awk 'NR==2{printf "%d", $7}')
    if [ $available_mem -lt 3 ]; then
        log_warning "Available memory is ${available_mem}GB. Minimum 4GB recommended."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    log_success "System requirements check passed"
}

# Function to install Docker and Docker Compose
install_docker() {
    log_info "Installing Docker and Docker Compose..."
    
    # Remove old versions
    sudo apt-get remove -y docker docker-engine docker.io containerd runc || true
    
    # Update package index
    sudo apt-get update
    
    # Install prerequisites
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        htop \
        ufw
    
    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    # Install Docker Compose (standalone)
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    # Start Docker service
    sudo systemctl enable docker
    sudo systemctl start docker
    
    log_success "Docker installation completed"
}

# Function to setup firewall
setup_firewall() {
    log_info "Configuring UFW firewall..."
    
    # Enable UFW
    sudo ufw --force enable
    
    # Allow SSH
    sudo ufw allow ssh
    
    # Allow HTTP and HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    
    # Allow specific application ports (internal access only)
    sudo ufw allow from 10.0.0.0/8 to any port 3000  # Grafana
    sudo ufw allow from 10.0.0.0/8 to any port 9090  # Prometheus
    
    log_success "Firewall configuration completed"
}

# Function to create service user
create_service_user() {
    log_info "Creating service user: $SERVICE_USER"
    
    if ! id "$SERVICE_USER" &>/dev/null; then
        sudo useradd -r -m -s /bin/bash $SERVICE_USER
        sudo usermod -aG docker $SERVICE_USER
        log_success "Service user created: $SERVICE_USER"
    else
        log_info "Service user already exists: $SERVICE_USER"
    fi
}

# Function to clone and setup application
setup_application() {
    log_info "Setting up application in $INSTALL_DIR..."
    
    # Create installation directory
    sudo mkdir -p $INSTALL_DIR
    sudo chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
    
    # Clone repository
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "Repository exists, pulling latest changes..."
        sudo -u $SERVICE_USER git -C $INSTALL_DIR pull origin $BRANCH
    else
        log_info "Cloning repository..."
        sudo -u $SERVICE_USER git clone -b $BRANCH $REPO_URL $INSTALL_DIR
    fi
    
    # Set permissions
    sudo chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
    
    log_success "Application setup completed"
}

# Function to configure environment
configure_environment() {
    log_info "Configuring environment variables..."
    
    ENV_FILE="$INSTALL_DIR/.env"
    
    if [ ! -f "$ENV_FILE" ]; then
        # Copy template
        sudo -u $SERVICE_USER cp $INSTALL_DIR/.env.enterprise $ENV_FILE
        
        # Generate secure secrets
        API_SECRET=$(openssl rand -base64 64)
        AUTH_SECRET=$(openssl rand -base64 64)
        SA_PASSWORD="AISupport_$(openssl rand -base64 12 | tr -d '=+/')"
        
        # Update environment file
        sudo -u $SERVICE_USER sed -i "s/your-super-secure-api-secret-key-change-this-in-production/$API_SECRET/g" $ENV_FILE
        sudo -u $SERVICE_USER sed -i "s/your-super-secure-auth-secret-key-change-this-in-production/$AUTH_SECRET/g" $ENV_FILE
        sudo -u $SERVICE_USER sed -i "s/SuperS3cureP@ssword123/$SA_PASSWORD/g" $ENV_FILE
        
        # Set external IP for ALLOWED_ORIGINS
        EXTERNAL_IP=$(curl -s ifconfig.me)
        sudo -u $SERVICE_USER sed -i "s/localhost/$EXTERNAL_IP/g" $ENV_FILE
        
        log_success "Environment configured with secure secrets"
        log_warning "Please update API keys in $ENV_FILE before starting the application"
    else
        log_info "Environment file already exists"
    fi
}

# Function to setup systemd service
setup_systemd_service() {
    log_info "Setting up systemd service..."
    
    cat << EOF | sudo tee /etc/systemd/system/support-ai.service > /dev/null
[Unit]
Description=Support AI Enterprise Platform
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.enterprise.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.enterprise.yml down
TimeoutStartSec=300
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable support-ai.service
    
    log_success "Systemd service created"
}

# Function to setup SSL with Let's Encrypt (optional)
setup_ssl() {
    log_info "Setting up SSL certificate with Let's Encrypt..."
    
    read -p "Enter your domain name (or press Enter to skip SSL setup): " DOMAIN
    
    if [ -n "$DOMAIN" ]; then
        # Install certbot
        sudo apt-get install -y certbot python3-certbot-nginx
        
        # Get certificate
        sudo certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
        
        # Update nginx configuration
        sudo -u $SERVICE_USER sed -i "s/server_name _;/server_name $DOMAIN;/" $INSTALL_DIR/nginx/nginx.conf
        
        log_success "SSL certificate obtained for $DOMAIN"
    else
        log_info "Skipping SSL setup"
    fi
}

# Function to start services
start_services() {
    log_info "Starting AI Platform services..."
    
    cd $INSTALL_DIR
    sudo -u $SERVICE_USER docker-compose -f docker-compose.enterprise.yml pull
    sudo systemctl start support-ai.service
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 30
    
    # Check service status
    if sudo -u $SERVICE_USER docker-compose -f docker-compose.enterprise.yml ps | grep -q "Up"; then
        log_success "Services started successfully"
        
        EXTERNAL_IP=$(curl -s ifconfig.me)
        echo
        log_success "🎉 Enterprise AI Platform deployed successfully!"
        echo
        log_info "Access URLs:"
        log_info "  • Main Application: http://$EXTERNAL_IP"
        log_info "  • Admin Dashboard: http://$EXTERNAL_IP/admin"
        log_info "  • Grafana (Internal): http://$EXTERNAL_IP:3000"
        log_info "  • Prometheus (Internal): http://$EXTERNAL_IP:9090"
        echo
        log_warning "Next steps:"
        log_warning "  1. Update API keys in $INSTALL_DIR/.env"
        log_warning "  2. Configure your domain and SSL certificate"
        log_warning "  3. Setup monitoring alerts"
        log_warning "  4. Configure backup strategy"
        
    else
        log_error "Some services failed to start. Check logs with:"
        log_error "  sudo -u $SERVICE_USER docker-compose -f $INSTALL_DIR/docker-compose.enterprise.yml logs"
    fi
}

# Main execution flow
main() {
    log_info "Starting Enterprise AI Platform deployment..."
    
    check_requirements
    install_docker
    setup_firewall
    create_service_user
    setup_application
    configure_environment
    setup_systemd_service
    setup_ssl
    
    # New shell for docker group to take effect
    log_info "Please log out and log back in for docker permissions to take effect, then run:"
    log_info "  sudo systemctl start support-ai.service"
    
    read -p "Start services now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_services
    else
        log_info "To start services later, run: sudo systemctl start support-ai.service"
    fi
}

# Run main function
main "$@"