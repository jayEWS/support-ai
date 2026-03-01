import messagebird
from app.core.config import settings
from app.core.logging import logger
import asyncio
import os
import urllib.request
from pydub import AudioSegment
import speech_recognition as sr

class BirdHandler:
    def __init__(self):
        if settings.BIRD_API_KEY != "YOUR_BIRD_API_KEY":
            self.client = messagebird.Client(settings.BIRD_API_KEY)
        else:
            self.client = None
            logger.warning("BIRD_API_KEY belum dikonfigurasi.")

    async def process_message(self, request, rag_engine):
        """Processes incoming webhooks from Bird."""
        try:
            payload = await request.json()
            logger.info(f"Bird Webhook Payload: {payload}")

            # Bird's webhook format for Conversations API
            msg_obj = payload.get('message', {})
            contact_obj = payload.get('contact', {})
            
            sender_id = contact_obj.get('id') or contact_obj.get('msisdn')
            
            # Detect Message Type (Text vs Audio)
            msg_type = msg_obj.get('type', 'text')
            query = ""
            is_audio = False
            
            if msg_type == 'text':
                query = msg_obj.get('content', {}).get('text', '')
            elif msg_type == 'audio':
                is_audio = True
                audio_url = msg_obj.get('content', {}).get('audio', {}).get('url')
                if audio_url:
                    query = await self._process_audio_url(audio_url, sender_id)
                else:
                    query = "Audio tak terbaca"

            if not sender_id or not query:
                return {"status": "ignored", "reason": "No sender or message content"}

            # Closure Logic
            closure_keywords = ["terima kasih", "thanks", "done", "selesai", "sudah cukup"]
            if any(k in query.lower() for k in closure_keywords):
                response_text = await rag_engine.finalize_ticket(sender_id)
                self.send_reply(sender_id, response_text)
            else:
                if is_audio:
                    # Request audio response back if user sent audio
                    text_resp, audio_url_path = await rag_engine.ask(query, user_id=sender_id, return_audio=True)
                    if audio_url_path: # Convert local path to a public reachable URL ideally, here we mock it
                        # For Bird API, it needs a public URL. In production, prefix with your server domain
                        public_audio_url = f"https://your-server-domain.com{audio_url_path}" 
                        self.send_reply(sender_id, text_resp, msg_type='audio', media_url=public_audio_url)
                    else:
                        self.send_reply(sender_id, text_resp)
                else:
                    response_text = await rag_engine.ask(query, user_id=sender_id)
                    self.send_reply(sender_id, response_text)
            
            return {"status": "success"}

        except Exception as e:
            logger.error(f"Error processing Bird message: {e}")
            return {"status": "error", "message": str(e)}

    async def _process_audio_url(self, audio_url: str, sender_id: str) -> str:
        """Downloads audio from Bird, converts to WAV, and transcribes to text."""
        try:
            # Setup temp paths
            temp_dir = os.path.join(settings.KNOWLEDGE_DIR, "..", "uploads", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            raw_audio_path = os.path.join(temp_dir, f"raw_{sender_id}.ogg")
            wav_audio_path = os.path.join(temp_dir, f"converted_{sender_id}.wav")
            
            # Download audio (assuming public or header auth isn't heavily needed for webhook media URLs here)
            await asyncio.to_thread(urllib.request.urlretrieve, audio_url, raw_audio_path)
            
            # Convert to WAV for SpeechRecognition
            audio = await asyncio.to_thread(AudioSegment.from_file, raw_audio_path)
            await asyncio.to_thread(audio.export, wav_audio_path, format="wav")
            
            # Transcribe
            r = sr.Recognizer()
            with sr.AudioFile(wav_audio_path) as source:
                audio_data = r.record(source)
                try:
                    # Let Google Speech Recognition auto-detect or try Indonesian primarily
                    text = r.recognize_google(audio_data, language="id-ID")
                    logger.info(f"Transcribed Audio: {text}")
                    return text
                except sr.UnknownValueError:
                    return "Maaf, aku tidak bisa mendengar suaranya dengan jelas."
                except sr.RequestError as e:
                    logger.error(f"Speech service error: {e}")
                    return "Sistem pengenal suara sedang gangguan, pesan audio diterima."
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return "Gagal memproses pesan audio."

    def send_reply(self, to, text, msg_type='text', media_url=None):
        """Sends a message using Bird Conversations API."""
        if not self.client:
            logger.error("Bird Client not initialized. Cannot send reply.")
            return

        try:
            # Note: Bird Conversations API often uses 'to' as the contact ID or MSISDN
            if msg_type == 'audio' and media_url:
                msg = self.client.conversation_create(
                    to,
                    {'type': 'audio', 'content': {'audio': {'url': media_url}}},
                    channelId=settings.WHATSAPP_CHANNEL_ID
                )
            else:
                msg = self.client.conversation_create(
                    to,
                    {'type': 'text', 'content': {'text': text}},
                    channelId=settings.WHATSAPP_CHANNEL_ID
                )
            logger.info(f"Bird Message Sent to {to}")
        except Exception as e:
            logger.error(f"Failed to send Bird message: {e}")
