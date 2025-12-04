from PIL import Image, ImageTk, ImageDraw, ImageSequence
import tkinter as tk
import os
import time
import threading

class UIElements:
    """Class for common UI elements"""
    
    @staticmethod
    def create_cup_image(size=(150, 150)):
        """Create a chai cup image using the provided image file"""
        # Path to the chai cup image
        image_path = os.path.join("assets", "cupimage.png")
        
        # Check if the image file exists
        if os.path.exists(image_path):
            try:
                # Load the image from file
                img = Image.open(image_path)
                
                # Resize the image to the specified size while maintaining aspect ratio
                img.thumbnail(size, Image.LANCZOS)
                
                # Convert to PhotoImage and return
                return ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error loading chai cup image: {e}")
                # Fall back to the drawn cup if there's an error
                return UIElements._create_fallback_cup_image(size)
        else:
            print(f"Chai cup image not found at: {image_path}")
            # Fall back to the drawn cup if the file doesn't exist
            return UIElements._create_fallback_cup_image(size)
    
    @staticmethod
    def _create_fallback_cup_image(size=(150, 150)):
        """Create a fallback chai cup image if the image file is not available"""
        img = Image.new('RGBA', size, (255, 255, 255, 0))
        
        # Draw a cup shape
        draw = ImageDraw.Draw(img)
        
        # Cup colors
        cup_color = "#e6a235"
        chai_color = "#b67a2d"
        saucer_color = "#f0e6d2"
        
        width, height = size
        
        # Draw saucer
        draw.ellipse((width//6, height*0.73, width*5/6, height*0.87), fill=saucer_color, outline="#d0c6b2")
        
        # Draw cup body
        draw.rectangle((width*0.27, height/3, width*0.73, height*0.73), fill=cup_color, outline="#d69b33")
        
        # Draw cup interior (chai)
        draw.rectangle((width*0.3, height*0.37, width*0.7, height*0.5), fill=chai_color)
        
        # Draw cup handle
        draw.arc((width*0.73, height*0.4, width*0.87, height*0.67), 270, 90, fill="#d69b33", width=5)
        
        # Draw steam
        for i in range(3):
            x = width*0.4 + i*width/10
            draw.arc((x, height*0.2, x+width/15, height*0.37), 180, 0, fill="#cccccc", width=2)
        
        return ImageTk.PhotoImage(img)
    
    @staticmethod
    def apply_button_style(button, color="#e6a235", text_color="white"):
        """Apply a consistent style to buttons"""
        button.config(
            bg=color,
            fg=text_color,
            relief="flat",
            padx=15,
            pady=5
        )
        
    @staticmethod
    def create_title_label(parent, text, large=True):
        """Create a styled title label"""
        if large:
            return tk.Label(
                parent, 
                text=text, 
                font=("Arial", 24, "bold"), 
                fg="#b67a2d", 
                bg="#f5f5f5"
            )
        else:
            return tk.Label(
                parent, 
                text=text, 
                font=("Arial", 18, "bold"), 
                fg="#b67a2d", 
                bg="#f5f5f5"
            )
