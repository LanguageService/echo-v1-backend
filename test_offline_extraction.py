import os
import sys
import django
from typing import Dict, Any

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from translation.services import DocumentTranslationService

def test_offline_extraction(file_path: str, target_lang: str = None):
    """
    Test the offline document extraction and optional translation functionality.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"\n--- Testing Offline {'Translation' if target_lang else 'Extraction'} for: {file_path} ---")
    if target_lang:
        print(f"Target Language: {target_lang}")
    
    service = DocumentTranslationService()
    
    # Open the file and pass it to the service
    with open(file_path, 'rb') as f:
        # Mock file object with 'name' attribute
        class MockFile(object):
            def __init__(self, file_obj, name):
                self.file_obj = file_obj
                self.name = name
            def read(self, *args, **kwargs):
                return self.file_obj.read(*args, **kwargs)
            def seek(self, *args, **kwargs):
                return self.file_obj.seek(*args, **kwargs)
            def __getattr__(self, name):
                return getattr(self.file_obj, name)
            def chunks(self):
                # Simulate Django's chunks()
                self.file_obj.seek(0)
                while True:
                    chunk = self.file_obj.read(1024*64)
                    if not chunk:
                        break
                    yield chunk

        mock_file = MockFile(f, os.path.basename(file_path))
        
        if target_lang:
            result = service.translate_document_offline(mock_file, target_lang)
        else:
            result = service.extract_document_text(mock_file)
        
        if result['success']:
            print(f"Success! Processed {result['total_blocks']} blocks.")
            print(f"File format: {result['file_format']}")
            print(f"Processing time: {result['processing_time']:.2f}s")
            
            blocks_to_show = result.get('translated_blocks', result.get('blocks', []))
            original_blocks = result.get('original_blocks', result.get('blocks', []))

            if 'translated_file_path' in result:
                print(f"\nTranslated file generated: {result['translated_file_path']}")
                if os.path.exists(result['translated_file_path']):
                    print(f"File size: {os.path.getsize(result['translated_file_path'])} bytes")
                else:
                    print("Warning: Translated file path was returned but file does not exist!")

            print("\nSample Blocks:")
            for i, block in enumerate(blocks_to_show[:5]):
                orig_text = original_blocks[i]['text']
                trans_text = block.get('translated_text', block['text'])
                
                print(f"[{i}] Original: {orig_text[:50]}...")
                if target_lang:
                    print(f"    Translated: {trans_text[:50]}...")
        else:
            print(f"Failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_offline_extraction.py <path_to_document> [target_language_code]")
    else:
        target = sys.argv[2] if len(sys.argv) > 2 else None
        test_offline_extraction(sys.argv[1], target)
