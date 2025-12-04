import cv2
import numpy as np
import requests
from PIL import Image, ImageTk, ImageDraw
import io

class QRUtils:
    """Utility class for QR code operations"""
    
    @staticmethod
    def load_qr_from_url(image_url):
        """Load a QR code image from a URL"""
        try:
            response = requests.get(image_url, stream=True)
            if response.status_code == 200:
                return Image.open(io.BytesIO(response.content))
            else:
                print(f"Failed to load QR image from URL: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error loading QR image: {e}")
            return None
    
    @staticmethod
    def detect_and_crop_qr(qr_image):
        """Detect and crop QR code from an image"""
        try:
            # Convert PIL image to OpenCV format
            cv_image = cv2.cvtColor(np.array(qr_image), cv2.COLOR_RGB2BGR)
            
            # Use OpenCV QRCodeDetector to detect and crop the QR code
            qr_detector = cv2.QRCodeDetector()
            retval, points = qr_detector.detect(cv_image)
            
            if retval and points is not None and len(points) > 0:
                # If QR code is detected, crop it
                # Reshape points for boundingRect
                points = points.reshape(-1, 2)  # Ensure correct shape for boundingRect
                
                # Get bounding rect from the points
                rect = cv2.boundingRect(points)
                x, y, w, h = rect
                
                # Add a small margin around the QR code for better visibility
                margin = 20  # Increased margin for better visibility
                x = max(0, x - margin)
                y = max(0, y - margin)
                w = min(cv_image.shape[1] - x, w + 2 * margin)
                h = min(cv_image.shape[0] - y, h + 2 * margin)
                
                # Crop the QR code
                cropped_qr = cv_image[y:y+h, x:x+w]
                
                # Convert back to PIL format
                cropped_qr_rgb = cv2.cvtColor(cropped_qr, cv2.COLOR_BGR2RGB)
                cropped_qr_image = Image.fromarray(cropped_qr_rgb)
                print(f"QR code successfully cropped to {w}x{h}")
                
                return cropped_qr_image
            else:
                print("QR code detection failed, using original image")
                return qr_image
                
        except Exception as e:
            print(f"Error in QR detection: {e}")
            return qr_image
    
    @staticmethod
    def create_qr_placeholder(width, height):
        """Create a placeholder QR code for demo purposes"""
        # Create a simple QR-like image
        img = Image.new('RGB', (width, height), color='white')
        
        # Draw a simple QR-like pattern
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([(0, 0), (width-1, height-1)], outline='black')
        
        # Draw QR code pattern (simplified)
        cell_size = width // 10
        for i in range(10):
            for j in range(10):
                if (i * j) % 3 == 0:  # Random pattern
                    draw.rectangle(
                        [(i * cell_size, j * cell_size), 
                         ((i+1) * cell_size, (j+1) * cell_size)], 
                        fill='black'
                    )
        
        return img
