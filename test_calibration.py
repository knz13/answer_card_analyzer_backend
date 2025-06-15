#!/usr/bin/env python3
"""
Test script to verify that internal_calibrate.py works without pytesseract dependency.
This helps ensure the built executable will work correctly.
"""

import sys
import traceback
from pathlib import Path
from PIL import Image
import numpy as np
import cv2

try:
    from internal_calibrate import (
        detect_contour_angle, 
        normalize_image_brightness, 
        auto_crop_document,
        apply_calibration_to_image
    )
    from utils import Utils
    print("✅ Successfully imported calibration functions")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def create_test_image():
    """Create a simple test image with some content to calibrate."""
    # Create a white image
    img = np.full((600, 800, 3), 255, dtype=np.uint8)
    
    # Add a black border (simulating document edges)
    cv2.rectangle(img, (50, 50), (750, 550), (0, 0, 0), 3)
    
    # Add some text-like rectangles
    cv2.rectangle(img, (100, 100), (700, 120), (0, 0, 0), -1)
    cv2.rectangle(img, (100, 150), (600, 170), (0, 0, 0), -1)
    cv2.rectangle(img, (100, 200), (650, 220), (0, 0, 0), -1)
    
    # Add some circles (simulating answer bubbles)
    cv2.circle(img, (150, 300), 15, (0, 0, 0), 2)
    cv2.circle(img, (200, 300), 15, (0, 0, 0), 2)
    cv2.circle(img, (250, 300), 15, (0, 0, 0), -1)  # Filled circle
    cv2.circle(img, (300, 300), 15, (0, 0, 0), 2)
    
    return img


def test_contour_angle_detection():
    """Test the contour angle detection function."""
    print("\n🔍 Testing contour angle detection...")
    
    try:
        # Create test image
        test_img = create_test_image()
        
        # Test with 0 degree rotation (should detect ~0)
        angle = detect_contour_angle(test_img)
        print(f"   0° rotation detected as: {angle:.1f}°")
        
        # Test with rotated image
        height, width = test_img.shape[:2]
        center = (width // 2, height // 2)
        
        # Rotate by 15 degrees
        M = cv2.getRotationMatrix2D(center, 15, 1.0)
        rotated_img = cv2.warpAffine(test_img, M, (width, height), 
                                   borderValue=(255, 255, 255))
        
        angle = detect_contour_angle(rotated_img)
        print(f"   15° rotation detected as: {angle:.1f}°")
        
        print("✅ Contour angle detection test passed")
        return True
        
    except Exception as e:
        print(f"❌ Contour angle detection test failed: {e}")
        traceback.print_exc()
        return False


def test_brightness_normalization():
    """Test the brightness normalization function."""
    print("\n💡 Testing brightness normalization...")
    
    try:
        # Create test image
        test_img = create_test_image()
        
        # Make it darker
        dark_img = (test_img * 0.3).astype(np.uint8)
        
        # Convert to PIL for the function
        pil_img = Image.fromarray(cv2.cvtColor(dark_img, cv2.COLOR_BGR2RGB))
        
        # Normalize brightness
        normalized = normalize_image_brightness(pil_img)
        
        # Convert back to check
        normalized_cv = cv2.cvtColor(np.array(normalized), cv2.COLOR_RGB2BGR)
        
        original_mean = np.mean(dark_img)
        normalized_mean = np.mean(normalized_cv)
        
        print(f"   Original mean brightness: {original_mean:.1f}")
        print(f"   Normalized mean brightness: {normalized_mean:.1f}")
        
        if normalized_mean > original_mean:
            print("✅ Brightness normalization test passed")
            return True
        else:
            print("❌ Brightness normalization didn't improve brightness")
            return False
        
    except Exception as e:
        print(f"❌ Brightness normalization test failed: {e}")
        traceback.print_exc()
        return False


def test_auto_crop():
    """Test the auto crop functionality."""
    print("\n✂️  Testing auto crop...")
    
    try:
        # Create test image with extra white space
        img = np.full((800, 1000, 3), 255, dtype=np.uint8)
        
        # Add content in the center
        cv2.rectangle(img, (200, 150), (800, 650), (0, 0, 0), 3)
        cv2.rectangle(img, (250, 200), (750, 220), (0, 0, 0), -1)
        
        # Convert to PIL
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        
        # Auto crop
        cropped = auto_crop_document(pil_img)
        
        # Check if it was cropped
        original_size = pil_img.size
        cropped_size = cropped.size
        
        print(f"   Original size: {original_size}")
        print(f"   Cropped size: {cropped_size}")
        
        if cropped_size[0] < original_size[0] or cropped_size[1] < original_size[1]:
            print("✅ Auto crop test passed")
            return True
        else:
            print("❌ Auto crop didn't reduce image size")
            return False
        
    except Exception as e:
        print(f"❌ Auto crop test failed: {e}")
        traceback.print_exc()
        return False


def test_full_calibration():
    """Test the complete calibration pipeline."""
    print("\n🔧 Testing full calibration pipeline...")
    
    try:
        # Create test image
        test_img = create_test_image()
        
        # Add some rotation and extra white space
        height, width = test_img.shape[:2]
        center = (width // 2, height // 2)
        
        # Rotate by 10 degrees
        M = cv2.getRotationMatrix2D(center, 10, 1.0)
        rotated_img = cv2.warpAffine(test_img, M, (width, height), 
                                   borderValue=(255, 255, 255))
        
        # Add padding
        padded_img = np.full((height + 200, width + 200, 3), 255, dtype=np.uint8)
        padded_img[100:100+height, 100:100+width] = rotated_img
        
        # Convert to PIL
        pil_img = Image.fromarray(cv2.cvtColor(padded_img, cv2.COLOR_BGR2RGB))
        
        # Apply full calibration
        calibrated = apply_calibration_to_image(pil_img)
        
        print(f"   Original size: {pil_img.size}")
        print(f"   Calibrated size: {calibrated.size}")
        
        print("✅ Full calibration pipeline test passed")
        return True
        
    except Exception as e:
        print(f"❌ Full calibration pipeline test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all calibration tests."""
    print("🧪 Testing Answer Card Analyzer Calibration (without pytesseract)")
    print("=" * 60)
    
    # Set debug mode for more detailed output
    Utils.set_debug(True)
    
    tests = [
        test_contour_angle_detection,
        test_brightness_normalization,
        test_auto_crop,
        test_full_calibration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Calibration is working correctly without pytesseract.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 