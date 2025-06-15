import cv2 as cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from utils import Utils


def auto_crop_document(img, padding_percent=0.005):
    """
    Automatically crop a scanned document to remove empty white spaces.
    
    Args:
        img: PIL Image or OpenCV image
        padding_percent: Percentage of padding to add around detected content (0.02 = 2%)
    
    Returns:
        Cropped PIL Image
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        original_pil = img
    else:
        cv_img = img
        original_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    # Show original image
    ##show_image(cv_img, "1_original_image")
    
    # Get original dimensions
    height, width = cv_img.shape[:2]
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    ##show_image(gray, "2_grayscale")
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    ##show_image(blurred, "3_blurred")
    
    # Create binary threshold - anything not white becomes black
    # Use adaptive threshold to handle varying lighting conditions
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 10)
    
    # Alternative: Simple threshold for high-contrast scans
    # _, thresh = cv2.threshold(blurred, 240, 255, cv2.THRESH_BINARY_INV)
    
    ##show_image(thresh, "4_threshold")
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        Utils.log_info("No contours found, returning original image")
        return original_pil
    
    # Show contours
    contour_img = cv_img.copy()
    cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)
    ##show_image(contour_img, "5_all_contours")
    
    # Method 1: Find the largest contour (main document)
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Show largest contour
    largest_contour_img = cv_img.copy()
    cv2.drawContours(largest_contour_img, [largest_contour], -1, (0, 0, 255), 3)
    ##show_image(largest_contour_img, "6_largest_contour")
    
    # Get bounding rectangle of the largest contour
    x, y, w, h = cv2.boundingRect(largest_contour)
    
    # Method 2: Alternative approach - find bounding box of all non-white pixels
    # This is more robust for documents with multiple separate elements
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) > 0:
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        
        # Use whichever method gives a more reasonable result
        contour_area = w * h
        coords_area = (x_max - x_min) * (y_max - y_min)
        
        # Show both bounding boxes for comparison
        comparison_img = cv_img.copy()
        # Contour-based box in blue
        cv2.rectangle(comparison_img, (x, y), (x + w, y + h), (255, 0, 0), 2)
        # Coordinate-based box in green
        cv2.rectangle(comparison_img, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        #show_image(comparison_img, "7_bounding_boxes_comparison")
        
        # If the coordinate-based method gives a significantly larger area, use it
        if coords_area > contour_area * 1.2:
            x, y, w, h = x_min, y_min, x_max - x_min, y_max - y_min
            Utils.log_info(f"Using coordinate-based bounding box (larger area)")
        else:
            Utils.log_info(f"Using contour-based bounding box")
    
    # Add padding
    padding_x = int(width * padding_percent)
    padding_y = int(height * padding_percent)
    
    # Expand the crop area with padding, but keep within image bounds
    x = max(0, x - padding_x)
    y = max(0, y - padding_y)
    w = min(width - x, w + 2 * padding_x)
    h = min(height - y, h + 2 * padding_y)
    
    # Ensure minimum reasonable size (at least 50% of original)
    min_width = int(width * 0.5)
    min_height = int(height * 0.5)
    
    if w < min_width or h < min_height:
        Utils.log_info("Detected crop area too small, returning original image")
        return original_pil
    
    # Draw the final crop rectangle on the image
    debug_img = cv_img.copy()
    cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 255), 4)  # Yellow rectangle
    cv2.putText(debug_img, f"CROP AREA: {w}x{h}", (x, y-10), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    ##show_image(debug_img, "8_final_crop_area")
    
    Utils.log_info(f"Cropping from ({x}, {y}) with size ({w}, {h})")
    Utils.log_info(f"Original size: ({width}, {height}), New size: ({w}, {h})")
    Utils.log_info(f"Size reduction: {((width * height - w * h) / (width * height) * 100):.1f}%")
    
    # Crop the original PIL image
    cropped_pil = original_pil.crop((x, y, x + w, y + h))
    
    # Show the final cropped result
    cropped_cv = cv2.cvtColor(np.array(cropped_pil), cv2.COLOR_RGB2BGR)
    ##show_image(cropped_cv, "9_final_cropped_result")
    
    return cropped_pil


def detect_document_corners(img):
    """
    Alternative method: Detect the four corners of a document using corner detection.
    Useful for documents that are tilted or have clear rectangular boundaries.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        cv_img = img
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edges = cv2.Canny(blurred, 75, 200)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    # Look for rectangular contours
    for contour in contours:
        # Approximate the contour
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # If we found a contour with 4 points, it might be our document
        if len(approx) == 4:
            return approx.reshape(4, 2)
    
    return None


def detect_contour_angle(img):
    """
    Detect the rotation angle using the largest contour in the image.
    This is often more reliable than text-based detection.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        cv_img = img
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Create binary threshold
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 10)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        Utils.log_info("No contours found for angle detection, returning 0")
        return 0
    
    # Find the largest contour (main document)
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Get the minimum area rectangle that fits this contour
    rect = cv2.minAreaRect(largest_contour)
    
    # Extract the angle from the rectangle
    # rect returns ((center_x, center_y), (width, height), angle)
    angle = rect[2]
    
    # OpenCV's minAreaRect returns angles in a specific way:
    # - The angle is between -90 and 0 degrees
    # - We need to adjust it to get the correct rotation
    
    # Get the dimensions of the rectangle
    width, height = rect[1]
    
    # If width > height, the rectangle is landscape
    # If height > width, the rectangle is portrait
    if width > height:
        # Landscape orientation
        if angle < -45:
            angle = 90 + angle
    else:
        # Portrait orientation  
        if angle < -45:
            angle = 90 + angle
        else:
            angle = angle
    
    # Limit the angle to reasonable rotation range
    if abs(angle) > 45:
        if angle > 0:
            angle = angle - 90
        else:
            angle = angle + 90
    
    if Utils.is_debug():
        # Draw the rotated rectangle for visualization
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        debug_img = cv_img.copy()
        cv2.drawContours(debug_img, [box], 0, (0, 255, 0), 3)
        cv2.putText(debug_img, f"Angle: {angle:.1f}°", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        #show_image(debug_img, "contour_angle_detection")
    
    Utils.log_info(f"Detected contour angle: {angle:.1f}°")
    return angle


def normalize_image_brightness(img):
    """
    Normalize image brightness using dynamic range stretching and gamma correction.
    Stretches the histogram to use the full 0-255 range, then applies gamma correction.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        was_pil = True
    else:
        cv_img = img
        was_pil = False
    
    # Show original for comparison
    if Utils.is_debug():
        ##show_image(cv_img, "0_original_before_normalization")
        pass
    
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Step 1: Dynamic Range Normalization - stretch histogram to use full 0-255 range
    min_val = np.min(gray)
    max_val = np.max(gray)
    
    if max_val > min_val:  # Avoid division by zero
        # Apply to all channels
        for i in range(3):
            cv_img[:, :, i] = ((cv_img[:, :, i] - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        
        if Utils.is_debug():
            ##show_image(cv_img, "1_range_stretched")
            Utils.log_info(f"Dynamic range: {min_val}-{max_val} → 0-255")
    else:
        Utils.log_info("Image has no dynamic range to stretch")
    
    # Step 2: Gamma Correction
    # Adjust overall brightness based on image characteristics
    mean_brightness = np.mean(cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY))
    
    if mean_brightness < 100:  # Too dark
        gamma = 0.7  # Brighten
        Utils.log_info(f"Image too dark (mean: {mean_brightness:.1f}), applying gamma: {gamma}")
    elif mean_brightness > 180:  # Too bright  
        gamma = 1.3  # Darken
        Utils.log_info(f"Image too bright (mean: {mean_brightness:.1f}), applying gamma: {gamma}")
    else:
        gamma = 1.0  # No gamma correction needed
        Utils.log_info(f"Image brightness OK (mean: {mean_brightness:.1f}), no gamma correction")
    
    if gamma != 1.0:
        # Build gamma correction lookup table
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        cv_img = cv2.LUT(cv_img, table)
        
        if Utils.is_debug():
            #show_image(cv_img, f"2_gamma_corrected_{gamma}")
            pass
    
    if Utils.is_debug():
        # Show before/after comparison
        original_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) if was_pil else img
        comparison = np.hstack((original_img, cv_img))
        ##show_image(comparison, "3_before_after_comparison")
    
    # Convert back to PIL if input was PIL
    if was_pil:
        result = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        return result
    else:
        return cv_img


def apply_calibration_to_image(img: Image, calibration_rect=None):
    # First, normalize brightness and contrast to handle varying lighting
    normalized_img = normalize_image_brightness(img)
    Utils.log_info("Applied brightness and contrast normalization")
    
    # Convert PIL Image to OpenCV format
    cv_img = cv2.cvtColor(np.array(normalized_img), cv2.COLOR_RGB2BGR)
    
    # Detect the angle using the normalized image (better for contour detection)
    angle = detect_contour_angle(cv_img)
    Utils.log_info(f"Using contour-based angle detection: {angle:.1f}°")
    
    # Get image dimensions
    height, width = cv_img.shape[:2]
    center = (width // 2, height // 2)
    
    # Get rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    if Utils.is_debug():
        #show_image(cv_img, "normalized_before_rotation")
        pass
    
    # Perform the rotation on the normalized image
    rotated = cv2.warpAffine(cv_img, M, (width, height), 
                           flags=cv2.INTER_CUBIC, 
                           borderMode=cv2.BORDER_CONSTANT, 
                           borderValue=(255, 255, 255))  # White background

    if Utils.is_debug():
        #show_image(rotated, "rotated_before_crop")
        pass
    
    if Utils.is_debug() and abs(angle) > 1:
        Utils.log_info(f"Applied rotation of {angle:.1f}°")
        pass
    
    # Convert back to PIL Image for cropping
    rotated_pil = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
    
    # Now, auto-crop the rotated image to remove empty spaces
    cropped_img = auto_crop_document(rotated_pil)
    
    return cropped_img

def show_image(image, text="image"):
    cv2.imshow(text, image)
    while True:
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cv2.destroyAllWindows()

def get_calibration_rect_for_image(img_path, img=None):
    if img is None:
        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    elif isinstance(img, Image.Image):
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    # Get image dimensions
    height, width = img.shape[:2]
    center = (width/2, height/2)
    
    # Get the angle
    angle = detect_contour_angle(img)
    
    # Create a rectangle that covers most of the image
    rect_width = width * 0.95  # 95% of image width
    rect_height = height * 0.95  # 95% of image height
    
    # Return in the format expected by the rest of the code
    return (center, (rect_width, rect_height), angle)

def get_calibration_center_for_image(image_path, img=None):
    if img is None:
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    elif isinstance(img, Image.Image):
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    height, width = img.shape[:2]
    return (width/2, height/2)  # Return center of image

if __name__ == "__main__":
    images = convert_from_path("examples/target_examples/Marianna Dias.pdf")
    image = images[0]
    
    # Test the auto-crop functionality
    cropped_image = auto_crop_document(image)
    
    # Test the new text-based angle detection
    rect = get_calibration_rect_for_image(None, img=cropped_image)
    rotated_image = apply_calibration_to_image(image, rect)
    
    # Display result
    cv_result = cv2.cvtColor(np.array(rotated_image), cv2.COLOR_RGB2BGR)
    #show_image(cv_result)
