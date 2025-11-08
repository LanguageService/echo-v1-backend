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
        """Handle voice processing with progress updates"""
        try:
            # Step 1: Audio preprocessing
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'audio_processing',
                'progress': 20,
                'message': 'Processing audio...'
            }))
            
            # Step 2: Speech to text
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'speech_to_text',
                'progress': 40,
                'message': 'Converting speech to text...'
            }))
            
            # Step 3: Translation
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'translation',
                'progress': 70,
                'message': 'Translating text...'
            }))
            
            # Step 4: Text to speech
            await self.send(text_data=json.dumps({
                'type': 'progress',
                'step': 'text_to_speech',
                'progress': 90,
                'message': 'Generating audio...'
            }))
            
            # Final result
            await self.send(text_data=json.dumps({
                'type': 'complete',
                'progress': 100,
                'result': {
                    'original_text': 'Hello world',
                    'translated_text': 'Hola mundo',
                    'source_language': 'en',
                    'target_language': 'es',
                    'audio_url': '/media/generated_audio.mp3'
                }
            }))
            
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