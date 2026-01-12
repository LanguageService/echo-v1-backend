import io
import wave
import struct

def generate_silent_wav_current(duration=1.0):
    print(f"Generating current logic for {duration}s")
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(44100) # 44.1kHz
        
        num_samples = int(44100 * duration)
        
        # Write silence (0)
        for _ in range(num_samples):
            wav_file.writeframes(struct.pack('h', 0))
            
    buffer.seek(0)
    data = buffer.read()
    print(f"Current Size: {len(data)} bytes")
    return data

def generate_silent_wav_optimized(duration=1.0):
    print(f"Generating optimized logic for {duration}s")
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(44100) # 44.1kHz
        
        num_samples = int(44100 * duration)
        
        # Write silence (0) - Optimized
        data = b'\x00\x02' * num_samples # wait this is not silence. Silence for signed 16-bit PCM is 0.
        # struct.pack('h', 0) is b'\x00\x00'
        data = b'\x00\x00' * num_samples
        wav_file.writeframes(data)
            
    buffer.seek(0)
    data = buffer.read()
    print(f"Optimized Size: {len(data)} bytes")
    return data

try:
    generate_silent_wav_current()
    generate_silent_wav_optimized()
except Exception as e:
    print(e)
