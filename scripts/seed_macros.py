"""
Seed comprehensive macros for Edgeworks Support Portal (61 macros).
Categories: Welcome, Acknowledgement, Troubleshooting,
  POS - FNB, POS - Retail, POS - Wholesale,
  Inventory, Report, Integration,
  Escalation, Follow-Up, Closing
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import db_manager

macros = [
    # ═══════════════  WELCOME (5)  ═══════════════
    {"name": "Welcome - Standard", "category": "Welcome",
     "content": "Hello {customer_name}! 👋 Welcome to Edgeworks Solutions Support.\n\nMy name is {agent_name}, and I'll be assisting you today.\n\nHow can I help you?"},
    {"name": "Welcome - Returning Customer", "category": "Welcome",
     "content": "Welcome back, {customer_name}! 👋 Great to hear from you again.\n\nI'm {agent_name}, how can I assist you today?"},
    {"name": "Welcome - After Hours", "category": "Welcome",
     "content": "Hi {customer_name}, thank you for reaching out to Edgeworks Solutions Support.\n\nOur office hours are Mon-Fri 9:00 AM - 6:00 PM (SGT). I'll log your request and our team will follow up with you during the next business day.\n\nIf this is urgent, please describe your issue and we'll prioritize it."},
    {"name": "Welcome - WhatsApp", "category": "Welcome",
     "content": "Hi {customer_name}! 👋 Thanks for reaching us on WhatsApp.\n\nI'm {agent_name} from Edgeworks Solutions Support. Please let me know what you need help with and I'll do my best to assist you."},
    {"name": "Welcome - New Customer", "category": "Welcome",
     "content": "Hello {customer_name}, welcome to Edgeworks Solutions! 🎉\n\nI'm {agent_name} and I'll be your support contact. May I know your outlet name and which Equip product you're using (POS / Inventory / Rewards)?\n\nThis will help me assist you more effectively."},

    # ═══════════════  ACKNOWLEDGEMENT (5)  ═══════════════
    {"name": "Acknowledge - Issue Received", "category": "Acknowledgement",
     "content": "Thank you for reporting this, {customer_name}. I understand the issue you're facing.\n\nLet me look into this for you right away."},
    {"name": "Acknowledge - Screenshot Received", "category": "Acknowledgement",
     "content": "Thank you for the screenshot, {customer_name}. I can see the issue clearly now.\n\nLet me investigate and get back to you shortly."},
    {"name": "Acknowledge - Urgent Issue", "category": "Acknowledgement",
     "content": "I understand this is urgent, {customer_name}. I'm treating this as a high-priority issue.\n\nLet me look into this immediately and keep you updated."},
    {"name": "Acknowledge - Investigating", "category": "Acknowledgement",
     "content": "Thank you for your patience, {customer_name}. I'm currently investigating your issue.\n\nI may need a few minutes to check with our technical team. I'll update you shortly."},
    {"name": "Acknowledge - Need More Info", "category": "Acknowledgement",
     "content": "Thank you for reaching out, {customer_name}.\n\nTo help me assist you better, could you provide:\n1. Your outlet name\n2. The Equip version you're using (V3 / V5)\n3. A screenshot or description of the error\n\nThis will help me resolve your issue faster."},

    # ═══════════════  TROUBLESHOOTING (6)  ═══════════════
    {"name": "Troubleshoot - Restart POS", "category": "Troubleshooting",
     "content": "Let's try a basic restart first:\n\n1. Close the Equip POS application completely\n2. Restart the POS terminal/PC\n3. Wait 30 seconds, then reopen Equip POS\n4. Try the operation again\n\nDoes the issue persist after restarting?"},
    {"name": "Troubleshoot - Network Check", "category": "Troubleshooting",
     "content": "This might be a network connectivity issue. Let's check:\n\n1. Verify your internet connection is working (try opening a browser)\n2. Check if the LAN cable is securely connected\n3. Restart your router/switch if needed\n4. If using WiFi, try switching to a wired connection\n\nOnce confirmed, please try the operation again."},
    {"name": "Troubleshoot - Printer Issue", "category": "Troubleshooting",
     "content": "For printer issues, please try:\n\n1. Check printer power and cable connections\n2. Ensure paper roll is loaded correctly (thermal side facing up)\n3. Restart the printer (turn off, wait 10s, turn on)\n4. In Equip POS, go to Settings > Printer and verify the correct printer is selected\n5. Print a test receipt\n\nIf it's still not working, please let me know the printer model."},
    {"name": "Troubleshoot - Cash Drawer", "category": "Troubleshooting",
     "content": "For cash drawer issues:\n\n1. Check if the RJ11 cable from the drawer to the printer is securely connected\n2. The cash drawer is triggered through the receipt printer — make sure the printer is working\n3. Try opening it manually using the key (underneath the drawer)\n4. In Equip POS Settings, verify the cash drawer kick code is correct\n\nDoes the drawer open when you print a receipt?"},
    {"name": "Troubleshoot - Login Issue", "category": "Troubleshooting",
     "content": "For login issues:\n\n1. Double-check your username and password (case-sensitive)\n2. Make sure Caps Lock is OFF\n3. If using PIN login, ensure the correct cashier PIN is being used\n4. Check if the POS can connect to the server (network icon in system tray)\n5. Try restarting the POS application\n\nIf you're still unable to log in, I can help reset your credentials."},
    {"name": "Troubleshoot - Slow Performance", "category": "Troubleshooting",
     "content": "If your POS is running slowly:\n\n1. Close any unnecessary applications running in the background\n2. Check available disk space (should have at least 2GB free)\n3. Restart the POS terminal\n4. Clear the POS transaction cache: Settings > System > Clear Cache\n5. Ensure your antivirus isn't running a scan during business hours\n\nIf the issue persists, we may need to check the database size."},

    # ═══════════════  POS - FNB (8)  ═══════════════
    {"name": "POS FNB - Table Management", "category": "POS - FNB",
     "content": "For table management in Equip POS (F&B):\n\n1. Go to the Table Layout screen from the main menu\n2. Tap on the table to open/create a new order\n3. To transfer a table: long-press the table > Transfer > select destination table\n4. To merge tables: long-press > Merge > select tables to combine\n5. To split bill: open the table > tap Split Bill > select items per guest\n\nNeed help with a specific table operation?"},
    {"name": "POS FNB - Menu Setup", "category": "POS - FNB",
     "content": "To set up your F&B menu in Equip POS:\n\n1. Go to Back Office > Item Master\n2. Click 'Add New Item'\n3. Fill in: Item Name, Category (e.g., Main Course, Drinks), Price\n4. For modifiers/add-ons: go to Modifier Group > create group > assign to items\n5. For combo/set meals: use the 'Bundle' feature under Item Type\n6. Assign items to POS buttons via Button Layout editor\n\nWould you like help with a specific menu configuration?"},
    {"name": "POS FNB - KDS Setup", "category": "POS - FNB",
     "content": "To set up Kitchen Display System (KDS):\n\n1. Ensure the KDS device is on the same network as the POS\n2. In Back Office > KDS Settings, add a new KDS station\n3. Assign item categories to each KDS station (e.g., Hot Kitchen, Cold Kitchen, Bar)\n4. Configure the display mode: Standard / Priority / By Course\n5. Set the alert timer for order preparation time\n6. Test by placing an order from POS and checking if it appears on KDS\n\nFor detailed steps, refer to the KDS Setup Guide."},
    {"name": "POS FNB - Modifier / Add-on", "category": "POS - FNB",
     "content": "To configure item modifiers/add-ons:\n\n1. Go to Back Office > Modifier Group\n2. Create a new modifier group (e.g., 'Doneness', 'Spice Level', 'Add-ons')\n3. Add modifier options with optional price adjustments\n4. Set min/max selections (e.g., must choose 1 spice level)\n5. Assign the modifier group to relevant menu items\n6. Test on POS — when ordering the item, modifiers should pop up\n\nCommon modifiers: Size (S/M/L), Sugar Level, Ice Level, Toppings, Cooking Preference."},
    {"name": "POS FNB - Service Charge & Tax", "category": "POS - FNB",
     "content": "To set up service charge and tax (F&B):\n\n1. Go to Back Office > Tax Settings\n2. GST/Tax: Set the tax rate (e.g., 9% GST for Singapore)\n3. Service Charge: Enable and set percentage (e.g., 10%)\n4. Choose tax calculation method: Tax-inclusive or Tax-exclusive pricing\n5. Apply to all items or specific categories\n\nReceipt will show: Subtotal + Service Charge + GST = Total\n\nNeed help with the tax calculation setup?"},
    {"name": "POS FNB - Takeaway / Dine-in", "category": "POS - FNB",
     "content": "To configure Takeaway vs Dine-in:\n\n1. In Back Office > Order Type, set up: Dine-in, Takeaway, Delivery\n2. You can configure different pricing per order type if needed\n3. Service charge can be set to apply only to Dine-in orders\n4. Takeaway packaging charges can be added as auto-modifiers\n5. On POS, cashier selects order type at the start of each transaction\n\nThis also affects which KDS station receives the order."},
    {"name": "POS FNB - Happy Hour Pricing", "category": "POS - FNB",
     "content": "To set up Happy Hour or time-based pricing:\n\n1. Go to Back Office > Promotion\n2. Create a new promotion with type 'Time-Based'\n3. Set the time window (e.g., 3:00 PM - 6:00 PM)\n4. Set the day(s) of the week it applies\n5. Choose discount type: percentage off, fixed price, or buy-1-get-1\n6. Assign to specific items or categories\n\nThe promotion will automatically activate during the set period."},
    {"name": "POS FNB - End of Day Closing", "category": "POS - FNB",
     "content": "For F&B End-of-Day closing:\n\n1. Ensure all tables are cleared and bills settled\n2. Go to Closing module on POS\n3. Count your actual cash in the drawer\n4. Enter the counted amount for reconciliation\n5. Review and resolve any discrepancies\n6. Confirm checkout to generate the Closing Report\n7. Print the Z-Report for your records\n\nTip: Always reconcile before closing to ensure accurate financial records."},

    # ═══════════════  POS - RETAIL (8)  ═══════════════
    {"name": "POS Retail - Barcode Scanning", "category": "POS - Retail",
     "content": "For barcode scanning issues in Retail POS:\n\n1. Ensure the barcode scanner is connected (USB or Bluetooth)\n2. Test the scanner by scanning into Notepad first\n3. In Equip POS, make sure the cursor is in the item search field\n4. Scan the barcode — it should auto-populate and add to cart\n5. If item not found: check if the barcode is registered in Item Master\n\nTo register a barcode: Back Office > Item Master > select item > enter barcode in 'Barcode' field."},
    {"name": "POS Retail - Item Master Setup", "category": "POS - Retail",
     "content": "To set up items in Retail POS:\n\n1. Go to Back Office > Item Master\n2. Click 'Add New Item'\n3. Fill in: Item Code, Item Name, Category, Brand\n4. Set pricing: Cost Price, Selling Price, Member Price\n5. Enter barcode (EAN-13, UPC, or custom)\n6. Set stock tracking: enable 'Track Inventory'\n7. Upload item image (optional)\n8. For variants (size/color): use the Item Variant feature\n\nYou can also bulk-import items using the Item Importer (Excel)."},
    {"name": "POS Retail - Member / Loyalty", "category": "POS - Retail",
     "content": "To set up membership and loyalty:\n\n1. Go to Back Office > Member Settings\n2. Create membership tiers (e.g., Silver, Gold, Platinum)\n3. Configure points earning: e.g., $1 spent = 1 point\n4. Set redemption rate: e.g., 100 points = $1 discount\n5. Set member-exclusive pricing per item if needed\n6. On POS, link member by phone number or member card scan\n\nFor Equip Rewards setup, refer to the Rewards & Redemption User Guide."},
    {"name": "POS Retail - Refund / Exchange", "category": "POS - Retail",
     "content": "To process a refund or exchange:\n\n1. On POS, go to Transaction > Refund\n2. Enter the original receipt number or scan the receipt barcode\n3. Select the item(s) to refund\n4. Choose refund method: Cash, Card, or Store Credit\n5. For exchange: process refund first, then ring up the new item\n6. Print refund receipt for customer signature\n\nNote: Refunds may require supervisor/manager approval depending on your settings."},
    {"name": "POS Retail - Promotion Setup", "category": "POS - Retail",
     "content": "To set up promotions in Retail POS:\n\n1. Go to Back Office > Promotion\n2. Create new promotion:\n   • Discount %: e.g., 20% off selected items\n   • Buy X Get Y: e.g., Buy 2 Get 1 Free\n   • Bundle Deal: e.g., 3 for $10\n   • Member-only promotions\n3. Set validity period (start/end date)\n4. Assign to specific items, categories, or brands\n5. Set priority if multiple promotions overlap\n\nYou can also import promotions via Excel file."},
    {"name": "POS Retail - Multi-store Pricing", "category": "POS - Retail",
     "content": "For multi-store pricing management:\n\n1. Go to Back Office > Price List\n2. Create price lists per outlet or region\n3. Assign different selling prices per price list\n4. Link each outlet to its respective price list\n5. Central price updates can be pushed to all outlets\n\nPrice changes sync automatically when the POS is connected to the server."},
    {"name": "POS Retail - Payment Methods", "category": "POS - Retail",
     "content": "To configure payment methods:\n\n1. Go to Back Office > Payment Type\n2. Default methods: Cash, NETS, Visa/Mastercard\n3. To add e-wallets: GrabPay, PayNow, FavePay, etc.\n4. Set rounding rules for cash payments\n5. Configure split payment if needed (allow multiple tenders per transaction)\n6. For terminal integration: ensure the card terminal is connected and configured\n\nNeed help setting up a specific payment method?"},
    {"name": "POS Retail - End of Day Closing", "category": "POS - Retail",
     "content": "For Retail End-of-Day closing:\n\n1. Go to Closing module on POS\n2. Count cash in the drawer\n3. Enter counted amount per payment type (Cash, NETS, Card)\n4. System shows expected vs actual — reconcile any differences\n5. Confirm checkout to close the shift\n6. Print Closing Report & Z-Report\n\nAfter closing, the POS starts a new shift for the next business day."},

    # ═══════════════  POS - WHOLESALE (6)  ═══════════════
    {"name": "POS Wholesale - Sales Order", "category": "POS - Wholesale",
     "content": "To create a Sales Order in Wholesale POS:\n\n1. Go to Sales > New Sales Order\n2. Select the customer (or create a new customer account)\n3. Add items by code, barcode, or search\n4. Apply customer-specific pricing or tiered discounts\n5. Set delivery date and remarks\n6. Save as Draft or Confirm the order\n7. Print the Sales Order for the warehouse\n\nConfirmed orders will appear in the Delivery Order queue."},
    {"name": "POS Wholesale - Purchase Order", "category": "POS - Wholesale",
     "content": "To create a Purchase Order (PO):\n\n1. Go to Inventory > Purchase Order\n2. Select the supplier\n3. Add items to order — system shows current stock level\n4. Enter order quantities and cost prices\n5. Review total amount and submit\n6. When goods arrive: go to Goods Receiving > select PO > confirm received quantities\n\nPO reference will link to the Goods Receiving Note (GRN) automatically."},
    {"name": "POS Wholesale - Customer Pricing", "category": "POS - Wholesale",
     "content": "To set up customer-specific pricing for wholesale:\n\n1. Go to Back Office > Customer Master\n2. Create or edit the customer account\n3. Assign a Price List (e.g., Tier 1, Tier 2, VIP)\n4. Set credit limit and payment terms (e.g., Net 30)\n5. For special pricing: use Contract Price per item per customer\n\nWhen this customer is selected at POS, their specific pricing applies automatically."},
    {"name": "POS Wholesale - Delivery Order", "category": "POS - Wholesale",
     "content": "To process a Delivery Order (DO):\n\n1. Go to Sales > Delivery Order\n2. Select the confirmed Sales Order to fulfill\n3. Enter actual delivered quantities (can be partial delivery)\n4. Print the DO for the delivery driver\n5. After delivery confirmation, convert DO to Invoice\n\nStock will be deducted upon DO confirmation."},
    {"name": "POS Wholesale - Invoice & Statement", "category": "POS - Wholesale",
     "content": "For invoicing and customer statements:\n\n1. Invoice is auto-generated from confirmed Delivery Orders\n2. Go to Sales > Invoice to view/print invoices\n3. For payment collection: Sales > Payment > apply to outstanding invoices\n4. To generate Customer Statement: Reports > Customer Statement > select customer & date range\n5. Statement shows all invoices, payments, and outstanding balance\n\nOverdue invoices will be highlighted in the aging report."},
    {"name": "POS Wholesale - Credit Note", "category": "POS - Wholesale",
     "content": "To issue a Credit Note:\n\n1. Go to Sales > Credit Note\n2. Reference the original Invoice number\n3. Select items to credit (returned/damaged goods)\n4. Enter quantities and reason\n5. Confirm to apply credit to customer's account\n\nThe credit will reduce the customer's outstanding balance and returned items will go back to inventory."},

    # ═══════════════  INVENTORY (7)  ═══════════════
    {"name": "Inventory - Stock Check", "category": "Inventory",
     "content": "To perform a stocktake:\n\n1. Go to Inventory > Stock Take\n2. Create a new stocktake session\n3. Select category/location or do a full count\n4. Scan or enter item barcodes and counted quantities\n5. System compares counted vs system stock\n6. Review variances and add remarks for discrepancies\n7. Approve to adjust stock levels\n\nTip: Do stocktake after closing hours for accuracy."},
    {"name": "Inventory - Stock Transfer", "category": "Inventory",
     "content": "To transfer stock between outlets:\n\n1. Go to Inventory > Stock Transfer\n2. Select 'From' outlet and 'To' outlet\n3. Add items and quantities to transfer\n4. Submit the Transfer Out request\n5. Receiving outlet: go to Stock Transfer > Pending > confirm received quantities\n\nStock is deducted from source upon transfer out and added to destination upon confirmation."},
    {"name": "Inventory - Goods Receiving", "category": "Inventory",
     "content": "To receive goods from suppliers:\n\n1. Go to Inventory > Goods Receiving Note (GRN)\n2. Select the Purchase Order (PO) reference\n3. Enter received quantities (may differ from ordered)\n4. Note any damaged/short items in remarks\n5. Confirm to update stock levels\n\nCost price will update based on the GRN if configured for weighted average costing."},
    {"name": "Inventory - Min/Max Reorder", "category": "Inventory",
     "content": "To set up automatic reorder levels:\n\n1. Go to Inventory > Item Master > select item\n2. Set 'Min Qty' (reorder point) and 'Max Qty' (reorder up-to level)\n3. When stock falls below Min, system flags it for reorder\n4. Go to Inventory > Replenishment to view items below Min\n5. System can auto-generate PO suggestions based on Min/Max\n\nRefer to the Stock Replenishment Training Guide for detailed setup."},
    {"name": "Inventory - Item Importer Excel", "category": "Inventory",
     "content": "To bulk import/update items via Excel:\n\n1. Go to Back Office > Item Importer\n2. Download the Excel template\n3. Fill in item details: Code, Name, Category, Barcode, Price, etc.\n4. Upload the completed Excel file\n5. Review the preview — system highlights errors in red\n6. Confirm to import\n\nThis supports both new item creation and bulk price/info updates."},
    {"name": "Inventory - Stock Adjustment", "category": "Inventory",
     "content": "To adjust stock manually (wastage, damage, samples):\n\n1. Go to Inventory > Stock Adjustment\n2. Select the outlet\n3. Add items and enter adjustment quantity (+/-)\n4. Select reason: Wastage, Damaged, Staff Use, Sample, Others\n5. Add remarks for audit trail\n6. Submit for approval (if approval workflow is enabled)\n\nAll adjustments are logged in the audit trail."},
    {"name": "Inventory - Web Portal Access", "category": "Inventory",
     "content": "To access the Inventory Web Portal:\n\n1. Open your browser and go to your Equip Inventory URL\n2. Log in with your admin credentials\n3. From the dashboard you can manage:\n   • Stock levels across all outlets\n   • Purchase Orders & Goods Receiving\n   • Stock Transfers between outlets\n   • Item Master & Category setup\n   • Inventory reports\n\nThe web portal gives you a centralized view across all locations."},

    # ═══════════════  REPORT (6)  ═══════════════
    {"name": "Report - Sales Summary", "category": "Report",
     "content": "To generate a Sales Summary Report:\n\n1. Go to Reports > Sales Report\n2. Select date range and outlet(s)\n3. Choose report type: Daily, Weekly, Monthly\n4. Filter by category, payment method, or cashier if needed\n5. Click Generate\n\nThe report shows: Total Sales, Discounts, Refunds, Net Sales, Transaction Count, and Average Basket Size."},
    {"name": "Report - Closing / Z-Report", "category": "Report",
     "content": "To access your Closing / Z-Report:\n\n1. Go to Reports > Closing Report\n2. Select the date and cashier/terminal\n3. The report shows:\n   • Total sales per payment type\n   • Expected vs actual cash count\n   • Over/short amount\n   • Void/refund transactions\n   • Discount summary\n\nYou can reprint past closing reports from this section."},
    {"name": "Report - Inventory Report", "category": "Report",
     "content": "To generate inventory reports:\n\n1. Go to Reports > Inventory\n2. Available reports:\n   • Stock Balance: Current stock across all outlets\n   • Stock Movement: In/out transactions per item\n   • Stock Valuation: Total inventory value at cost\n   • Low Stock Alert: Items below reorder level\n   • Aging Report: Slow-moving items\n3. Export to Excel or PDF for further analysis."},
    {"name": "Report - Best Seller Analysis", "category": "Report",
     "content": "To see your best-selling items:\n\n1. Go to Reports > Item Sales Analysis\n2. Select date range and outlet\n3. Sort by: Quantity Sold, Revenue, or Profit\n4. View Top 10 / Top 50 / All items\n5. Compare across periods to identify trends\n\nThis helps with purchasing decisions and menu/product optimization."},
    {"name": "Report - Hourly Sales", "category": "Report",
     "content": "To view hourly sales breakdown:\n\n1. Go to Reports > Hourly Sales\n2. Select date and outlet\n3. The report shows sales per hour in a chart and table\n4. Identify peak hours for staffing optimization\n5. Compare weekday vs weekend patterns\n\nThis is useful for F&B outlets to plan staff scheduling and prep times."},
    {"name": "Report - Export to Excel", "category": "Report",
     "content": "To export any report to Excel:\n\n1. Generate the report with your desired filters\n2. Click the 'Export' button (Excel icon) at the top right\n3. Choose format: Excel (.xlsx) or CSV\n4. The file will download to your computer\n\nAll reports in Equip support Excel export for further analysis or accounting purposes."},

    # ═══════════════  INTEGRATION (6)  ═══════════════
    {"name": "Integration - GrabFood", "category": "Integration",
     "content": "For GrabFood integration with Equip POS:\n\n1. Ensure the GrabFood integration module is enabled\n2. GrabFood orders will automatically appear on POS as new orders\n3. The order type will be tagged as 'GrabFood'\n4. Items will map to your Equip menu items\n5. Accept/reject orders from the POS\n6. Status updates sync back to GrabFood\n\nIf orders are not coming through, check the integration status in Back Office > Integration."},
    {"name": "Integration - FoodPanda/Deliveroo", "category": "Integration",
     "content": "For FoodPanda / Deliveroo integration:\n\n1. Integration is managed through the Equip Back Office\n2. Go to Settings > Integration > select the platform\n3. Enter your merchant credentials and store ID\n4. Map your delivery platform menu to Equip items\n5. Orders will flow into POS automatically\n\nIf you're experiencing sync issues, please check your API credentials and contact us for assistance."},
    {"name": "Integration - E-commerce Sync", "category": "Integration",
     "content": "For e-commerce integration (Magento/Shopify):\n\n1. Equip can sync items, stock, and pricing with your online store\n2. Online orders flow into Equip for fulfillment\n3. Stock levels sync in real-time to prevent overselling\n4. To set up: Back Office > Integration > E-commerce\n5. Enter your store URL and API credentials\n\nFor Proseller-Magento sync: refer to 'Resync Item from Proseller to Magento' guide."},
    {"name": "Integration - Payment Terminal", "category": "Integration",
     "content": "For payment terminal integration:\n\n1. Equip POS supports integration with NETS, UOB, OCBC, DBS terminals\n2. Connect the terminal to POS via USB or LAN\n3. In Back Office > Payment Settings, enable terminal integration\n4. Select the terminal model and communication port\n5. Test with a small transaction\n\nThe amount will be sent from POS to terminal automatically — no manual keying needed."},
    {"name": "Integration - Accounting Software", "category": "Integration",
     "content": "For accounting software integration:\n\n1. Equip can export daily sales data to Xero or QuickBooks\n2. Go to Back Office > Integration > Accounting\n3. Connect your accounting account via API\n4. Map your Equip payment types to accounting categories\n5. Sales data will sync daily after closing\n\nThis eliminates manual data entry for your accounts team."},
    {"name": "Integration - Self-Checkout Kiosk", "category": "Integration",
     "content": "For Self-Checkout Kiosk setup:\n\n1. The kiosk runs on the Equip Self-Checkout module\n2. Menu/items sync from the main POS system\n3. Supports QR payment (PayNow, GrabPay) and card payment\n4. Orders appear on KDS just like regular POS orders\n5. Kiosk can be configured for F&B (order-at-table) or Retail\n\nRefer to the Self-Checkout Kiosk User Guide for detailed setup."},

    # ═══════════════  ESCALATION (4)  ═══════════════
    {"name": "Escalate - Technical Team", "category": "Escalation",
     "content": "{customer_name}, I've reviewed your issue and it requires deeper technical investigation.\n\nI'm escalating this to our technical team now. They will:\n1. Review the details I've documented\n2. Contact you within 1 business day\n3. May request remote access if needed\n\nYour ticket reference will be shared with you. Thank you for your patience."},
    {"name": "Escalate - Developer Team", "category": "Escalation",
     "content": "{customer_name}, this appears to be a software-level issue that our development team needs to investigate.\n\nI've created a ticket with all the details and screenshots you provided. Our developer team will analyze this and we'll update you with a fix or workaround.\n\nEstimated response time: 1-2 business days for non-critical issues."},
    {"name": "Escalate - Remote Access", "category": "Escalation",
     "content": "{customer_name}, to diagnose this issue further, our team would like to perform a remote session.\n\nHere's what we need:\n1. Confirm a suitable date and time\n2. Ensure the POS terminal has internet access\n3. We'll use TeamViewer/AnyDesk — we'll provide the download link\n\nOur technician will guide you through the entire process. Would you like to schedule this?"},
    {"name": "Escalate - On-site Visit", "category": "Escalation",
     "content": "{customer_name}, after reviewing your issue, we believe an on-site visit is needed to resolve this.\n\nI'll arrange for our field technician to visit your outlet. Could you confirm:\n1. Outlet address\n2. Preferred date and time\n3. Contact person on-site\n\nWe'll confirm the appointment once scheduled."},

    # ═══════════════  FOLLOW-UP (4)  ═══════════════
    {"name": "Follow-Up - Status Update", "category": "Follow-Up",
     "content": "Hi {customer_name}, just a quick update on your support ticket.\n\nOur team is actively working on your issue. We'll have an update for you within the next [timeframe].\n\nThank you for your patience. We'll keep you posted."},
    {"name": "Follow-Up - Issue Resolved", "category": "Follow-Up",
     "content": "Hi {customer_name}, great news! 🎉\n\nThe issue you reported has been resolved. Here's what was done:\n[describe fix]\n\nPlease verify on your end and let us know if everything is working as expected.\n\nThank you for your patience!"},
    {"name": "Follow-Up - Pending Reply", "category": "Follow-Up",
     "content": "Hi {customer_name}, following up on our previous conversation.\n\nWe're waiting for your confirmation/response to proceed.\n\nCould you please check and let us know? If you need more time, that's perfectly fine — just let me know and I'll keep your ticket open."},
    {"name": "Follow-Up - Software Update", "category": "Follow-Up",
     "content": "Hi {customer_name}, a software update is available for your Equip system.\n\nThe update includes bug fixes and improvements relevant to your recent issue.\n\nWould you like us to schedule the update? We recommend doing it after business hours to avoid disruption."},

    # ═══════════════  CLOSING (6)  ═══════════════
    {"name": "Closing - Standard", "category": "Closing",
     "content": "Dear {customer_name} @ {company},\n\nIs there anything else we can assist you with?\n\nIf there are no further questions at this time, I'll proceed to close this chat.\n\nHowever, please feel free to reopen it anytime if the issue hasn't been fully resolved, I'll be happy to continue supporting you.\n\nThank you for contacting Edgeworks Solutions Support. Have a nice day!"},
    {"name": "Closing - Warm Follow-up", "category": "Closing",
     "content": "Dear {customer_name} @ {company},\n\nIf you have any further questions or concerns, please don't hesitate to reach out.\n\nWe are here to help and want to ensure you're completely satisfied with our service.\n\nThank you once again for your time and understanding. We truly value your business and look forward to continuing to support you."},
    {"name": "Closing - Quick Resolved", "category": "Closing",
     "content": "Dear {customer_name} @ {company},\n\nGlad we could help! If you experience any further issues, don't hesitate to reach out.\n\nThank you for contacting Edgeworks Solutions Support. Have a great day! 😊"},
    {"name": "Closing - Ticket Created", "category": "Closing",
     "content": "Dear {customer_name} @ {company},\n\nWe've created a support ticket for your issue. Our team will review and follow up shortly.\n\nIn the meantime, if you have any additional information that might help us resolve this faster, please feel free to share it here.\n\nThank you for your patience. We'll keep you updated on the progress!"},
    {"name": "Closing - Resolved Next Steps", "category": "Closing",
     "content": "Dear {customer_name} @ {company},\n\nI'm glad we were able to resolve your issue today.\n\nAs a reminder, here's what was done:\n• [Summary of resolution]\n\nIf you experience any related issues, please don't hesitate to contact us again.\n\nThank you for choosing Edgeworks Solutions. Have a wonderful day! 😊"},
    {"name": "Closing - Pending Resolution", "category": "Closing",
     "content": "Dear {customer_name} @ {company},\n\nThank you for your patience today. While we weren't able to fully resolve the issue during this session, rest assured our team is continuing to work on it.\n\nWe will update you via [email/WhatsApp] once we have a solution.\n\nIn the meantime, if the issue worsens or you have additional information, please reach out anytime.\n\nThank you for contacting Edgeworks Solutions Support."},
]

if __name__ == "__main__":
    created = 0
    skipped = 0
    for m in macros:
        try:
            db_manager.create_macro(m["name"], m["content"], m["category"])
            print(f"  [+] {m['category']:20s} | {m['name']}")
            created += 1
        except Exception as e:
            print(f"  [!] SKIP {m['name']}: {e}")
            skipped += 1

    print(f"\nDone! {created} created, {skipped} skipped (already exist).")

    all_macros = db_manager.get_macros()
    categories = {}
    for m in all_macros:
        cat = m["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nTotal macros in DB: {len(all_macros)}")
    print("By category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:20s} : {count}")
