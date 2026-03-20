import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


class OCRConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user is AnonymousUser:
            await self.close()
            return
            
        self.group_name = f"ocr_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ocr_process':
                await self.send(text_data=json.dumps({
                    'type': 'processing_started',
                    'status': 'Processing your image...',
                    'progress': 0
                }))
                
                # This will be integrated with the OCR service
                await self.process_ocr_request(data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))

    async def process_ocr_request(self, data):
        """Handle OCR processing with progress updates"""
        try:
            # Step 1: Image preprocessing
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'preprocessing',
                'progress': 25,
                'message': 'Optimizing image...'
            }))
            
            # Step 2: Text extraction
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'ocr',
                'progress': 50,
                'message': 'Extracting text...'
            }))
            
            # Step 3: Language detection
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'language',
                'progress': 75,
                'message': 'Detecting language...'
            }))
            
            # Step 4: Translation
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'translation',
                'progress': 90,
                'message': 'Translating text...'
            }))
            
            # Final result (placeholder)
            await self.send(text_data=json.dumps({
                'type': 'complete',
                'progress': 100,
                'result': {
                    'original_text': 'Sample text',
                    'translated_text': 'Texto de muestra',
                    'language': 'en',
                    'target_language': 'es'
                }
            }))
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Processing failed: {str(e)}'
            }))

    # Message handlers for group communication
    async def processing_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def processing_complete(self, event):
        await self.send(text_data=json.dumps(event['data']))



class VoiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user is AnonymousUser:
            await self.close()
            return
            
        self.group_name = f"voice_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'voice_process':
                await self.send(text_data=json.dumps({
                    'type': 'processing_started',
                    'status': 'Processing your audio...',
                    'progress': 0
                }))
                
                await self.process_voice_request(data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))

    async def process_voice_request(self, data):
        """Handle voice processing with orchestral service"""
        import base64
        import io
        from asgiref.sync import sync_to_async
        from translation.orchestrator import TranslationOrchestrator
        
        try:
            # 1. Validation and Setup
            audio_base64 = data.get('audio')
            target_lang = data.get('target_language', 'en')
            source_lang = data.get('source_language', 'auto')
            
            if not audio_base64:
                raise Exception("No audio data provided")

            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'preprocessing',
                'progress': 20,
                'message': 'Decoding audio...'
            }))
            
            # 2. Decode audio
            audio_bytes = base64.b64decode(audio_base64)
            audio_io = io.BytesIO(audio_bytes)
            
            # 3. Call Orchestrator (Sync to Async)
            orchestrator = TranslationOrchestrator()
            
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'processing',
                'progress': 50,
                'message': 'Processing translation...'
            }))
            
            # Use sync_to_async since orchestrator is currently synchronous
            # We wrap it to be able to use it in this async consumer
            def run_orchestrator():
                return orchestrator.translate_speech(
                    user=self.user,
                    audio_file=audio_io,
                    target_lang=target_lang,
                    source_lang=source_lang,
                    mode='SHORT'
                )
            
            result = await sync_to_async(run_orchestrator)()
            
            if result['success']:
                # Final result
                await self.send(text_data=json.dumps({
                    'type': 'complete',
                    'progress': 100,
                    'result': {
                        'translation_id': result.get('translation_id'),
                        'original_text': result.get('transcript'),
                        'translated_text': result.get('translation'),
                        'source_language': source_lang,
                        'target_language': target_lang,
                        'audio_url': result.get('translated_audio_url')
                    }
                }))
            else:
                raise Exception(result.get('error', 'Processing failed'))
                
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Processing failed: {str(e)}'
            }))

    async def processing_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def processing_complete(self, event):
        await self.send(text_data=json.dumps(event['data']))



class ProcessingConsumer(AsyncWebsocketConsumer):
    """Generic processing consumer for background tasks"""
    async def connect(self):
        self.user = self.scope["user"]
        if self.user is AnonymousUser:
            await self.close()
            return
            
        self.group_name = f"processing_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # Handle different processing types
            await self.send(text_data=json.dumps({
                'type': 'acknowledgment',
                'message': 'Processing request received'
            }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))

    async def task_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def task_complete(self, event):
        await self.send(text_data=json.dumps(event['data']))
