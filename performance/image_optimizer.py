"""
Image preprocessing and optimization for better OCR performance
"""
import os
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ImageOptimizer:
    """Optimize images for better OCR accuracy and faster processing"""
    
    def __init__(self):
        self.max_width = 1920
        self.max_height = 1080
        self.min_width = 300
        self.min_height = 200
        self.target_dpi = 300
        
    def optimize_for_ocr(self, image_path: str, output_path: Optional[str] = None) -> str:
        """
        Comprehensive image optimization for OCR processing
        Returns path to optimized image
        """
        try:
            if output_path is None:
                base, ext = os.path.splitext(image_path)
                output_path = f"{base}_optimized{ext}"
            
            # Load image with OpenCV for better control
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            original_height, original_width = img.shape[:2]
            
            # Step 1: Resize if necessary
            img = self._resize_image(img, original_width, original_height)
            
            # Step 2: Convert to grayscale if needed
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # Step 3: Enhance contrast and remove noise
            enhanced = self._enhance_image(gray)
            
            # Step 4: Apply OCR-specific optimizations
            optimized = self._apply_ocr_optimizations(enhanced)
            
            # Save optimized image
            cv2.imwrite(output_path, optimized)
            
            logger.info(f"Image optimized: {image_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Image optimization failed: {str(e)}")
            # Return original path if optimization fails
            return image_path
    
    def _resize_image(self, img: np.ndarray, width: int, height: int) -> np.ndarray:
        """Resize image to optimal dimensions"""
        # Don't resize if already in good range
        if (self.min_width <= width <= self.max_width and 
            self.min_height <= height <= self.max_height):
            return img
        
        # Calculate scale factor
        scale_w = self.max_width / width if width > self.max_width else 1.0
        scale_h = self.max_height / height if height > self.max_height else 1.0
        scale = min(scale_w, scale_h)
        
        # Don't upscale small images too much
        if width < self.min_width or height < self.min_height:
            scale = max(self.min_width / width, self.min_height / height)
            scale = min(scale, 2.0)  # Max 2x upscale
        
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Use high-quality interpolation
        if scale < 1.0:
            interpolation = cv2.INTER_AREA  # Best for downscaling
        else:
            interpolation = cv2.INTER_CUBIC  # Best for upscaling
        
        return cv2.resize(img, (new_width, new_height), interpolation=interpolation)
    
    def _enhance_image(self, gray_img: np.ndarray) -> np.ndarray:
        """Enhance image contrast and reduce noise"""
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray_img)
        
        # Reduce noise with bilateral filter
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        return denoised
    
    def _apply_ocr_optimizations(self, img: np.ndarray) -> np.ndarray:
        """Apply OCR-specific image optimizations"""
        # Sharpen the image slightly
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(img, -1, kernel)
        
        # Ensure good contrast
        # Apply adaptive thresholding to handle varying lighting
        binary = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Remove small noise with morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def quick_optimize(self, image_path: str) -> str:
        """Fast optimization for time-sensitive processing"""
        try:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_quick{ext}"
            
            # Use PIL for faster processing
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Quick resize if too large
                if img.width > self.max_width or img.height > self.max_height:
                    img.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)
                
                # Quick contrast enhancement
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.2)
                
                # Quick sharpening
                img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=2))
                
                img.save(output_path, optimize=True, quality=95)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Quick optimization failed: {str(e)}")
            return image_path
    
    def get_image_info(self, image_path: str) -> Dict[str, Any]:
        """Get detailed image information for optimization decisions"""
        try:
            with Image.open(image_path) as img:
                info = {
                    'width': img.width,
                    'height': img.height,
                    'mode': img.mode,
                    'format': img.format,
                    'size_kb': os.path.getsize(image_path) / 1024,
                    'aspect_ratio': img.width / img.height,
                    'needs_resize': (img.width > self.max_width or 
                                   img.height > self.max_height or
                                   img.width < self.min_width or 
                                   img.height < self.min_height),
                    'optimization_recommended': True
                }
                
                # Add DPI info if available
                if hasattr(img, 'info') and 'dpi' in img.info:
                    info['dpi'] = img.info['dpi']
                
                return info
                
        except Exception as e:
            logger.error(f"Could not get image info: {str(e)}")
            return {'error': str(e)}
    
    def batch_optimize(self, image_paths: list, output_dir: str) -> Dict[str, str]:
        """Optimize multiple images in batch"""
        results = {}
        
        os.makedirs(output_dir, exist_ok=True)
        
        for image_path in image_paths:
            try:
                filename = os.path.basename(image_path)
                base, ext = os.path.splitext(filename)
                output_path = os.path.join(output_dir, f"{base}_optimized{ext}")
                
                optimized_path = self.optimize_for_ocr(image_path, output_path)
                results[image_path] = optimized_path
                
            except Exception as e:
                logger.error(f"Batch optimization failed for {image_path}: {str(e)}")
                results[image_path] = image_path  # Return original on failure
        
        return results
    
    def estimate_processing_time(self, image_path: str) -> Dict[str, float]:
        """Estimate processing time for different optimization levels"""
        try:
            info = self.get_image_info(image_path)
            
            # Base time estimates (in seconds)
            pixel_count = info.get('width', 1000) * info.get('height', 1000)
            base_time = pixel_count / 1000000  # 1 second per megapixel baseline
            
            estimates = {
                'quick_optimize': base_time * 0.3,
                'full_optimize': base_time * 0.8,
                'ocr_processing': base_time * 1.5  # Estimated OCR time
            }
            
            return estimates
            
        except Exception:
            return {
                'quick_optimize': 0.5,
                'full_optimize': 1.0,
                'ocr_processing': 2.0
            }


# Global optimizer instance
image_optimizer = ImageOptimizer()