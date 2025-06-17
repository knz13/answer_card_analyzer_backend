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
    # if Utils.is_debug():
    #     show_image(cv_img, "crop_1_original_image")
    
    # Get original dimensions
    height, width = cv_img.shape[:2]
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    # if Utils.is_debug():
    #     show_image(gray, "crop_2_grayscale")
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # if Utils.is_debug():
    #     show_image(blurred, "crop_3_blurred")
    
    # Create binary threshold - anything not white becomes black
    # Use adaptive threshold to handle varying lighting conditions
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 10)
    
    # Alternative: Simple threshold for high-contrast scans
    #_, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY_INV)
    
    # if Utils.is_debug():
    #     show_image(thresh, "crop_4_threshold")
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        Utils.log_info("No contours found, returning original image")
        return original_pil
    
    # Show contours
    contour_img = cv_img.copy()
    cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)
    # if Utils.is_debug():
    #     show_image(contour_img, "crop_5_all_contours")
    
    # Method 1: Find the largest contour (main document)
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Show largest contour
    largest_contour_img = cv_img.copy()
    cv2.drawContours(largest_contour_img, [largest_contour], -1, (0, 0, 255), 3)
    # if Utils.is_debug():
    #     show_image(largest_contour_img, "crop_6_largest_contour")
    
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
        # if Utils.is_debug():
        #     show_image(comparison_img, "crop_7_bounding_boxes_comparison")
        
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
        # if Utils.is_debug():
        #     show_image(cv_img, "crop_8_no_crop_too_small")
        return original_pil
    
    # Draw the final crop rectangle on the image
    debug_img = cv_img.copy()
    cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 255), 4)  # Yellow rectangle
    cv2.putText(debug_img, f"CROP AREA: {w}x{h}", (x, y-10), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    # if Utils.is_debug():
    #     show_image(debug_img, "crop_8_final_crop_area")
    
    Utils.log_info(f"Cropping from ({x}, {y}) with size ({w}, {h})")
    Utils.log_info(f"Original size: ({width}, {height}), New size: ({w}, {h})")
    Utils.log_info(f"Size reduction: {((width * height - w * h) / (width * height) * 100):.1f}%")
    
    # Crop the original PIL image
    cropped_pil = original_pil.crop((x, y, x + w, y + h))
    
    # Show the final cropped result
    cropped_cv = cv2.cvtColor(np.array(cropped_pil), cv2.COLOR_RGB2BGR)
    # if Utils.is_debug():
    #     show_image(cropped_cv, "crop_9_final_cropped_result")
    
    return cropped_pil


def detect_document_corners(img):
    """
    Enhanced method: Detect the four corners of a document using corner detection.
    Useful for documents that are tilted or have clear rectangular boundaries.
    Returns the four corner points for perspective correction.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        cv_img = img
    
    Utils.log_info("Attempting to detect document corners for perspective correction")
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Try multiple edge detection strategies
    edges_methods = [
        {"name": "adaptive_canny", "params": {"low": 50, "high": 150}},
        {"name": "adaptive_canny", "params": {"low": 30, "high": 100}},
        {"name": "adaptive_canny", "params": {"low": 75, "high": 200}}
    ]
    
    best_corners = None
    best_score = 0
    
    for method in edges_methods:
        # Edge detection
        edges = cv2.Canny(blurred, method["params"]["low"], method["params"]["high"])
        
        # Apply morphological operations to close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        Utils.log_info(f"Edge method {method['name']} found {len(contours)} contours")
        
        # Look for rectangular contours
        for i, contour in enumerate(contours[:10]):  # Check top 10 contours
            area = cv2.contourArea(contour)
            if area < (cv_img.shape[0] * cv_img.shape[1] * 0.1):  # Too small
                continue
                
            # Approximate the contour
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Try different epsilon values if 4 corners not found
            for eps_mult in [0.015, 0.025, 0.03, 0.035]:
                if len(approx) != 4:
                    epsilon = eps_mult * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                if len(approx) == 4:
                    break
            
            # If we found a contour with 4 points
            if len(approx) == 4:
                corners = approx.reshape(4, 2)
                
                # Validate the corners (should form a reasonable quadrilateral)
                score = validate_document_corners(corners, cv_img.shape)
                Utils.log_info(f"Found 4-point contour with score: {score:.3f}")
                
                if score > best_score and score > 0.5:  # Minimum quality threshold
                    best_corners = corners
                    best_score = score
                    Utils.log_info(f"New best corners found with score: {score:.3f}")
                    
                    # if Utils.is_debug():
                    #     debug_img = cv_img.copy()
                    #     cv2.drawContours(debug_img, [approx], -1, (0, 255, 0), 3)
                    #     for j, corner in enumerate(corners):
                    #         cv2.circle(debug_img, tuple(corner), 10, (255, 0, 0), -1)
                    #         cv2.putText(debug_img, str(j), tuple(corner + 15), 
                    #                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    #     show_image(debug_img, f"corners_method_{method['name']}_contour_{i}")
                
                # If we found a very good match, no need to continue
                if score > 0.9:
                    break
        
        # If we found a very good match, no need to try other methods
        if best_score > 0.9:
            break
    
    if best_corners is not None:
        Utils.log_info(f"Final best corners detected with score: {best_score:.3f}")
        return order_corners(best_corners)
    else:
        Utils.log_info("No valid document corners found")
        return None


def validate_document_corners(corners, img_shape):
    """
    Validate detected corners to ensure they form a reasonable document rectangle.
    Returns a score between 0 and 1 (higher is better).
    """
    if len(corners) != 4:
        return 0
    
    h, w = img_shape[:2]
    score = 0
    
    # Check if corners are within image bounds
    if np.all(corners >= 0) and np.all(corners[:, 0] < w) and np.all(corners[:, 1] < h):
        score += 0.2
    else:
        return 0  # Invalid if any corner is outside image
    
    # Calculate area of the quadrilateral
    area = cv2.contourArea(corners)
    img_area = w * h
    area_ratio = area / img_area
    
    # Area should be reasonable (between 10% and 95% of image)
    if 0.1 <= area_ratio <= 0.95:
        score += 0.3 * min(area_ratio / 0.5, (1 - area_ratio) / 0.05)
    
    # Check if the quadrilateral is approximately rectangular
    # Calculate all side lengths
    ordered = order_corners(corners)
    sides = []
    for i in range(4):
        p1 = ordered[i]
        p2 = ordered[(i + 1) % 4]
        sides.append(np.linalg.norm(p2 - p1))
    
    # Opposite sides should be similar
    top_bottom_ratio = min(sides[0], sides[2]) / max(sides[0], sides[2])
    left_right_ratio = min(sides[1], sides[3]) / max(sides[1], sides[3])
    
    score += 0.25 * (top_bottom_ratio + left_right_ratio) / 2
    
    # Check angles (should be close to 90 degrees for a rectangle)
    angles = []
    for i in range(4):
        p1 = ordered[(i - 1) % 4]
        p2 = ordered[i]
        p3 = ordered[(i + 1) % 4]
        
        v1 = p1 - p2
        v2 = p3 - p2
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        angle = np.arccos(np.clip(cos_angle, -1, 1))
        angles.append(abs(angle - np.pi/2))  # Deviation from 90 degrees
    
    avg_angle_deviation = np.mean(angles)
    angle_score = max(0, 1 - (avg_angle_deviation / (np.pi/4)))  # Normalize to 0-1
    score += 0.25 * angle_score
    
    return score


def order_corners(corners):
    """
    Order corners in a consistent way: top-left, top-right, bottom-right, bottom-left.
    """
    # Sort by Y coordinate (top to bottom)
    corners = corners[np.argsort(corners[:, 1])]
    
    # Get top two and bottom two points
    top_two = corners[:2]
    bottom_two = corners[2:]
    
    # Sort top two by X coordinate (left to right)
    top_two = top_two[np.argsort(top_two[:, 0])]
    
    # Sort bottom two by X coordinate (left to right)
    bottom_two = bottom_two[np.argsort(bottom_two[:, 0])]
    
    # Return in order: top-left, top-right, bottom-right, bottom-left
    return np.array([top_two[0], top_two[1], bottom_two[1], bottom_two[0]], dtype=np.float32)


def detect_contour_angle(img):
    """
    Detect the rotation angle using the blackest parts of the image.
    Uses percentile-based method to ignore outliers and find main content bounds.
    Returns both angle and the bounding rectangle.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        cv_img = img
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # Create aggressive threshold to get only the blackest parts (text/content)
    # Use a lower threshold value to capture only the darkest pixels
    _, thresh = cv2.threshold(blurred, 30, 255, cv2.THRESH_BINARY_INV)
    
    # Apply morphological operations to connect nearby text
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Find all black pixels (text/content pixels)
    black_pixels = np.column_stack(np.where(thresh > 0))
    
    if len(black_pixels) == 0:
        Utils.log_info("No black pixels found for angle detection, returning 0")
        return 0, None
    
    Utils.log_info(f"Total black pixels found: {len(black_pixels)}")
    
    # Try different percentile values if the first one doesn't work well
    percentile_options = [1, 3, 5, 8]  # Less aggressive options
    angle = 0
    crop_rect = None
    filtered_pixels_xy = None
    
    for percentile in percentile_options:
        Utils.log_info(f"Trying percentile: {percentile}%")
        
        y_coords = black_pixels[:, 0]
        x_coords = black_pixels[:, 1]
        
        # Calculate percentile-based bounds to ignore outliers
        y_min_percentile = int(np.percentile(y_coords, percentile))
        y_max_percentile = int(np.percentile(y_coords, 100 - percentile))
        x_min_percentile = int(np.percentile(x_coords, percentile))
        x_max_percentile = int(np.percentile(x_coords, 100 - percentile))
        
        # Filter black pixels to only those within percentile bounds
        mask = ((y_coords >= y_min_percentile) & (y_coords <= y_max_percentile) & 
                (x_coords >= x_min_percentile) & (x_coords <= x_max_percentile))
        
        filtered_black_pixels = black_pixels[mask]
        
        Utils.log_info(f"Filtered pixels with {percentile}% percentile: {len(filtered_black_pixels)} (kept {len(filtered_black_pixels)/len(black_pixels)*100:.1f}%)")
        
        if len(filtered_black_pixels) < 100:  # Need minimum pixels for reliable angle detection
            Utils.log_info(f"Not enough filtered pixels ({len(filtered_black_pixels)}), trying next percentile")
            continue
        
        # Convert to (x, y) format for minimum area rectangle
        filtered_pixels_xy = np.array([(pt[1], pt[0]) for pt in filtered_black_pixels], dtype=np.int32)
        
        # Get the minimum area rectangle that fits the filtered pixels
        rect = cv2.minAreaRect(filtered_pixels_xy)
        
        # Extract the angle from the rectangle
        angle = rect[2]
        
        # Get the dimensions of the rectangle
        width, height = rect[1]
        
        Utils.log_info(f"Raw angle from minAreaRect: {angle:.2f}°, dimensions: {width:.1f}x{height:.1f}")
        
        # Adjust angle based on rectangle orientation
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
        
        Utils.log_info(f"Adjusted angle: {angle:.2f}°")
        
        # If we got a reasonable angle (not exactly 0), use this result
        if abs(angle) > 0.5:  # More than 0.5 degrees
            Utils.log_info(f"Found good angle {angle:.2f}° with {percentile}% percentile")
            
            # Get the bounding rectangle coordinates using percentile bounds
            x_min, x_max = x_min_percentile, x_max_percentile
            y_min, y_max = y_min_percentile, y_max_percentile
            
            # Add some padding (0.2% of image dimensions)
            img_height, img_width = cv_img.shape[:2]
            padding_x = int(img_width * 0.002)
            padding_y = int(img_height * 0.002)
            
            # Apply padding but keep within image bounds
            crop_rect = {
                'x': max(0, x_min - padding_x),
                'y': max(0, y_min - padding_y),
                'width': min(img_width - max(0, x_min - padding_x), (x_max - x_min) + 2 * padding_x),
                'height': min(img_height - max(0, y_min - padding_y), (y_max - y_min) + 2 * padding_y)
            }
            
            break
    
    # If we still don't have a good result, fall back to simple bounding box
    if abs(angle) <= 0.5 or crop_rect is None:
        Utils.log_info("Percentile method failed, falling back to simple bounding box")
        
        # Use all black pixels for bounding box
        y_coords = black_pixels[:, 0]
        x_coords = black_pixels[:, 1]
        
        x_min, x_max = np.min(x_coords), np.max(x_coords)
        y_min, y_max = np.min(y_coords), np.max(y_coords)
        
        # Add padding
        img_height, img_width = cv_img.shape[:2]
        padding_x = int(img_width * 0.002)
        padding_y = int(img_height * 0.002)
        
        crop_rect = {
            'x': max(0, x_min - padding_x),
            'y': max(0, y_min - padding_y),
            'width': min(img_width - max(0, x_min - padding_x), (x_max - x_min) + 2 * padding_x),
            'height': min(img_height - max(0, y_min - padding_y), (y_max - y_min) + 2 * padding_y)
        }
        
        # Try to get angle from all pixels as fallback
        all_pixels_xy = np.array([(pt[1], pt[0]) for pt in black_pixels], dtype=np.int32)
        rect = cv2.minAreaRect(all_pixels_xy)
        angle = rect[2]
        width, height = rect[1]
        
        # Apply same angle adjustments
        if width > height:
            if angle < -45:
                angle = 90 + angle
        else:
            if angle < -45:
                angle = 90 + angle
        
        if abs(angle) > 45:
            if angle > 0:
                angle = angle - 90
            else:
                angle = angle + 90
                
        Utils.log_info(f"Fallback angle: {angle:.2f}°")
    
    # Draw visualization for debugging
    """ if Utils.is_debug() and filtered_pixels_xy is not None:
        debug_img = cv_img.copy()
        
        # Draw all filtered black pixels in blue (sample to avoid clutter)
        if len(filtered_pixels_xy) > 1000:
            sample_indices = np.random.choice(len(filtered_pixels_xy), 1000, replace=False)
            sample_pixels = filtered_pixels_xy[sample_indices]
        else:
            sample_pixels = filtered_pixels_xy
            
        for pt in sample_pixels:
            cv2.circle(debug_img, (int(pt[0]), int(pt[1])), 1, (255, 0, 0), -1)
        
        # Draw the minimum area rectangle in green
        rect = cv2.minAreaRect(filtered_pixels_xy)
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        cv2.drawContours(debug_img, [box], 0, (0, 255, 0), 3)
        
        # Draw the crop rectangle in yellow
        cv2.rectangle(debug_img, (crop_rect['x'], crop_rect['y']), 
                     (crop_rect['x'] + crop_rect['width'], crop_rect['y'] + crop_rect['height']), 
                     (0, 255, 255), 3)
        
        # Add text info
        cv2.putText(debug_img, f"Angle: {angle:.1f}°", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(debug_img, f"Filtered pixels: {len(filtered_pixels_xy)}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        cv2.putText(debug_img, f"Total pixels: {len(black_pixels)}", (10, 110), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        cv2.putText(debug_img, f"Rect: {width:.0f}x{height:.0f}", (10, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(debug_img, f"Crop: {crop_rect['width']}x{crop_rect['height']}", (10, 190), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        show_image(debug_img, "2_percentile_based_angle_detection") """
    
    Utils.log_info(f"Final detected angle using percentile-based method: {angle:.1f}°")
    Utils.log_info(f"Crop rectangle: {crop_rect}")
    
    return angle, crop_rect


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
    # if Utils.is_debug():
    #     show_image(cv_img, "norm_0_original_before_normalization")
    
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Step 1: Dynamic Range Normalization - stretch histogram to use full 0-255 range
    min_val = np.min(gray)
    max_val = np.max(gray)
    
    if max_val > min_val:  # Avoid division by zero
        # Apply to all channels
        for i in range(3):
            cv_img[:, :, i] = ((cv_img[:, :, i] - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        
        # if Utils.is_debug():
        #     show_image(cv_img, "norm_1_range_stretched")
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
        
        # if Utils.is_debug():
        #     show_image(cv_img, f"norm_2_gamma_corrected_{gamma}")
    
    # if Utils.is_debug():
    #     # Show before/after comparison
    #     original_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) if was_pil else img
    #     comparison = np.hstack((original_img, cv_img))
    #     show_image(comparison, "norm_3_before_after_comparison")
    
    # Convert back to PIL if input was PIL
    if was_pil:
        result = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        return result
    else:
        return cv_img


def apply_calibration_to_image(img: Image, calibration_rect=None, padding_percent=0.005):
    # Show original image
    # if Utils.is_debug():
    #     cv_original = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    #     show_image(cv_original, "0_original_input")
    
    # First, normalize brightness and contrast to handle varying lighting
    normalized_img = normalize_image_brightness(img)
    Utils.log_info("Applied brightness and contrast normalization")
    
    # Show normalized image
    # if Utils.is_debug():
    #     cv_normalized = cv2.cvtColor(np.array(normalized_img), cv2.COLOR_RGB2BGR)
    #     show_image(cv_normalized, "1_after_normalization")
    
    # Convert PIL Image to OpenCV format
    cv_img = cv2.cvtColor(np.array(normalized_img), cv2.COLOR_RGB2BGR)
    
    # Use angle from calibration_rect if provided, otherwise detect it
    if False:
        # Extract angle from calibration_rect tuple: (center, (width, height), angle)
        angle = calibration_rect[2]
        crop_rect = None  # When using provided calibration_rect, we don't have crop info
        Utils.log_info(f"Using provided angle from calibration_rect: {angle:.1f}°")
        
        # Create transform info for legacy compatibility
        transform_info = {
            'type': 'rotation',
            'angle': angle,
            'crop_rect': None
        }
    else:
        # Detect both rotation and perspective/shear distortion
        transform_info = detect_shear_and_perspective(cv_img)
        
        if transform_info['type'] == 'perspective':
            Utils.log_info(f"Using perspective correction (distortion: {transform_info['distortion_score']:.3f})")
        else:
            method = transform_info.get('method', 'unknown')
            Utils.log_info(f"Using rotation correction ({transform_info['angle']:.1f}°) via {method}")
            
            # Add padding to the crop_rect for rotation-only correction
            if transform_info['crop_rect'] is not None:
                crop_rect = transform_info['crop_rect']
                crop_rect['x'] = crop_rect['x'] - padding_percent * crop_rect['width']
                crop_rect['y'] = crop_rect['y'] - padding_percent * crop_rect['height']
                crop_rect['width'] = crop_rect['width'] + 2 * padding_percent * crop_rect['width']
                crop_rect['height'] = crop_rect['height'] + 2 * padding_percent * crop_rect['height']
                transform_info['crop_rect'] = crop_rect
    
    # Apply the appropriate transformation (rotation or perspective)
    if transform_info['type'] == 'perspective':
        # Apply perspective correction
        corrected_img = apply_perspective_correction(cv_img, transform_info)
        
        # For perspective correction, auto-crop to remove any remaining white space
        final_img = auto_crop_document(corrected_img, padding_percent)
        
    else:
        # Apply rotation correction (legacy path)
        height, width = cv_img.shape[:2]
        center = (width // 2, height // 2)
        
        # Get rotation matrix
        M = cv2.getRotationMatrix2D(center, transform_info['angle'], 1.0)

        # if Utils.is_debug():
        #     show_image(cv_img, "2_before_rotation")
        
        # Perform the rotation on the normalized image
        rotated = cv2.warpAffine(cv_img, M, (width, height), 
                               flags=cv2.INTER_CUBIC, 
                               borderMode=cv2.BORDER_CONSTANT, 
                               borderValue=(255, 255, 255))  # White background

        # if Utils.is_debug():
        #     show_image(rotated, "3_after_rotation")
        
        if Utils.is_debug() and abs(transform_info['angle']) > 1:
            Utils.log_info(f"Applied rotation of {transform_info['angle']:.1f}°")
            pass
        
        # Convert back to PIL Image for cropping
        rotated_pil = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))
        
        # Show before cropping
        # if Utils.is_debug():
        #     show_image(rotated, "4_before_crop")
        
        # Use crop rectangle from angle detection if available, otherwise use auto-crop
        if transform_info['crop_rect'] is not None:
            Utils.log_info(f"Using crop rectangle from angle detection: {transform_info['crop_rect']}")
            
            # Apply the crop rectangle
            final_img = rotated_pil.crop((
                transform_info['crop_rect']['x'], 
                transform_info['crop_rect']['y'], 
                transform_info['crop_rect']['x'] + transform_info['crop_rect']['width'], 
                transform_info['crop_rect']['y'] + transform_info['crop_rect']['height']
            ))
            
            # if Utils.is_debug():
            #     # Show the crop rectangle on the rotated image
            #     debug_crop = rotated.copy()
            #     cv2.rectangle(debug_crop, (transform_info['crop_rect']['x'], transform_info['crop_rect']['y']), 
            #                  (transform_info['crop_rect']['x'] + transform_info['crop_rect']['width'], 
            #                   transform_info['crop_rect']['y'] + transform_info['crop_rect']['height']), 
            #                  (0, 255, 255), 3)
            #     cv2.putText(debug_crop, f"CROP: {transform_info['crop_rect']['width']}x{transform_info['crop_rect']['height']}", 
            #                (transform_info['crop_rect']['x'], transform_info['crop_rect']['y']-10), 
            #                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            #     show_image(debug_crop, "4_crop_rectangle_applied")
            
        else:
            Utils.log_info("No crop rectangle available, using auto-crop")
            # Fallback to auto-crop (when using provided calibration_rect)
            final_img = auto_crop_document(rotated_pil, padding_percent)
    
    # Show final result
    # if Utils.is_debug():
    #     cv_final = cv2.cvtColor(np.array(final_img), cv2.COLOR_RGB2BGR)
    #     show_image(cv_final, "5_final_result")
    
    return final_img

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
    
    # Get the angle (we don't need the crop_rect here since this function 
    # is used when calibration_rect is provided to apply_calibration_to_image)
    angle, _ = detect_contour_angle(img)
    
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

def detect_shear_and_perspective(img):
    """
    Detect both rotation and shear/perspective distortion.
    Returns transformation matrix for perspective correction if shear is detected,
    otherwise returns simple rotation angle.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        cv_img = img
    
    Utils.log_info("Detecting shear and perspective distortion")
    
    # First try to detect document corners for perspective correction
    corners = detect_document_corners(cv_img)
    
    if corners is not None:
        Utils.log_info("Document corners detected, checking for perspective distortion")
        
        # Check if there's significant perspective distortion
        h, w = cv_img.shape[:2]
        
        # Calculate the ideal rectangle corners
        ideal_corners = np.array([
            [0, 0],
            [w, 0], 
            [w, h],
            [0, h]
        ], dtype=np.float32)
        
        # Check how much the detected corners deviate from ideal rectangle
        perspective_score = calculate_perspective_distortion(corners, ideal_corners)
        
        Utils.log_info(f"Perspective distortion score: {perspective_score:.3f}")
        
        if perspective_score > 0.05:  # Significant distortion threshold
            Utils.log_info("Significant perspective distortion detected, will use perspective correction")
            
            # Calculate transformation matrix for perspective correction
            # Create target rectangle with some padding
            padding = min(w, h) * 0.02
            target_corners = np.array([
                [padding, padding],
                [w - padding, padding],
                [w - padding, h - padding],
                [padding, h - padding]
            ], dtype=np.float32)
            
            transform_matrix = cv2.getPerspectiveTransform(corners, target_corners)
            
            return {
                'type': 'perspective',
                'matrix': transform_matrix,
                'corners': corners,
                'target_corners': target_corners,
                'distortion_score': perspective_score
            }
    
    # If no significant perspective distortion, try Hough line skew detection
    Utils.log_info("No significant perspective distortion, trying Hough line skew detection")
    hough_angle = detect_hough_line_skew(cv_img)
    
    if abs(hough_angle) > 0.5:  # Significant skew detected
        Utils.log_info(f"Hough line skew detection found {hough_angle:.2f}° skew")
        
        # For simple skew correction, we'll use rotation
        angle, crop_rect = hough_angle, None
        
        # Try to get crop rectangle from contour detection
        _, crop_rect = detect_contour_angle(cv_img)
        
        return {
            'type': 'rotation',
            'angle': angle,
            'crop_rect': crop_rect,
            'method': 'hough_lines'
        }
    
    # Fallback to contour-based rotation detection
    Utils.log_info("No significant skew from Hough lines, using contour-based rotation detection")
    angle, crop_rect = detect_contour_angle(cv_img)
    
    return {
        'type': 'rotation',
        'angle': angle,
        'crop_rect': crop_rect,
        'method': 'contour_analysis'
    }


def calculate_perspective_distortion(detected_corners, ideal_corners):
    """
    Calculate how much the detected corners deviate from an ideal rectangle.
    Returns a score where 0 = perfect rectangle, higher = more distortion.
    """
    # Normalize coordinates to 0-1 range
    h, w = ideal_corners[2, 1], ideal_corners[2, 0]
    norm_detected = detected_corners / np.array([w, h])
    norm_ideal = ideal_corners / np.array([w, h])
    
    # Calculate average distance between corresponding corners
    distances = np.linalg.norm(norm_detected - norm_ideal, axis=1)
    avg_distance = np.mean(distances)
    
    return avg_distance


def apply_perspective_correction(img, transform_info):
    """
    Apply perspective correction using the detected transformation.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        was_pil = True
    else:
        cv_img = img
        was_pil = False
    
    height, width = cv_img.shape[:2]
    
    if transform_info['type'] == 'perspective':
        Utils.log_info(f"Applying perspective correction (distortion score: {transform_info['distortion_score']:.3f})")
        
        # Apply perspective transformation
        corrected = cv2.warpPerspective(cv_img, transform_info['matrix'], (width, height),
                                      flags=cv2.INTER_CUBIC,
                                      borderMode=cv2.BORDER_CONSTANT,
                                      borderValue=(255, 255, 255))
        
        # if Utils.is_debug():
        #     # Show the transformation
        #     debug_img = cv_img.copy()
        #     cv2.drawContours(debug_img, [transform_info['corners'].astype(int)], -1, (0, 255, 0), 3)
        #     for i, corner in enumerate(transform_info['corners']):
        #         cv2.circle(debug_img, tuple(corner.astype(int)), 8, (255, 0, 0), -1)
        #         cv2.putText(debug_img, str(i), tuple((corner + 15).astype(int)), 
        #                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        #     show_image(debug_img, "perspective_corners_detected")
        #     show_image(corrected, "perspective_corrected")
        
        # For perspective correction, we'll crop to remove the padding
        padding = min(width, height) * 0.02
        cropped = corrected[int(padding):int(height-padding), int(padding):int(width-padding)]
        
    else:  # rotation correction
        Utils.log_info(f"Applying rotation correction ({transform_info['angle']:.1f}°)")
        
        center = (width // 2, height // 2)
        M = cv2.getRotationMatrix2D(center, transform_info['angle'], 1.0)
        
        corrected = cv2.warpAffine(cv_img, M, (width, height),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(255, 255, 255))
        cropped = corrected  # Will crop later using crop_rect
    
    # Convert back to PIL if needed
    if was_pil:
        return Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
    else:
        return cropped

def detect_hough_line_skew(img):
    """
    Detect document skew using Hough line detection.
    This method works well for documents with clear text lines.
    Returns the skew angle in degrees.
    """
    # Convert PIL Image to OpenCV format if needed
    if isinstance(img, Image.Image):
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    else:
        cv_img = img
    
    Utils.log_info("Detecting skew using Hough line transform")
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # Create binary image to enhance text
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Apply morphological operations to connect text elements
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))  # Horizontal kernel to connect text
    morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # Find edges
    edges = cv2.Canny(morphed, 50, 150, apertureSize=3)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
    
    if lines is None:
        Utils.log_info("No lines detected with Hough transform")
        return 0
    
    Utils.log_info(f"Detected {len(lines)} lines with Hough transform")
    
    # Analyze line angles
    angles = []
    for line in lines:
        rho, theta = line[0]
        # Convert theta to angle in degrees
        # theta is in radians, 0 to pi
        angle = np.degrees(theta)
        
        # Focus on nearly horizontal lines (text lines)
        # Convert to range -90 to 90 degrees
        if angle > 90:
            angle = angle - 180
        elif angle < -90:
            angle = angle + 180
            
        # Only consider lines that are roughly horizontal (within 45 degrees)
        if abs(angle) <= 45:
            angles.append(angle)
    
    if not angles:
        Utils.log_info("No horizontal lines found for skew detection")
        return 0
    
    # Calculate the most common angle (mode)
    angles = np.array(angles)
    
    # Use histogram to find the most common angle
    hist, bin_edges = np.histogram(angles, bins=90, range=(-45, 45))
    max_bin_idx = np.argmax(hist)
    skew_angle = (bin_edges[max_bin_idx] + bin_edges[max_bin_idx + 1]) / 2
    
    # Alternatively, use median for robustness
    median_angle = np.median(angles)
    
    # Choose the angle with better support
    if hist[max_bin_idx] >= len(angles) * 0.3:  # At least 30% of lines agree
        final_angle = skew_angle
        Utils.log_info(f"Using histogram mode angle: {final_angle:.2f}° (support: {hist[max_bin_idx]}/{len(angles)})")
    else:
        final_angle = median_angle
        Utils.log_info(f"Using median angle: {final_angle:.2f}° (insufficient consensus for mode)")
    
    Utils.log_info(f"Detected skew angle using Hough lines: {final_angle:.2f}°")
    
    # if Utils.is_debug():
    #     # Visualize the detected lines
    #     debug_img = cv_img.copy()
    #     if lines is not None:
    #         for line in lines[:50]:  # Show first 50 lines
    #             rho, theta = line[0]
    #             a = np.cos(theta)
    #             b = np.sin(theta)
    #             x0 = a * rho
    #             y0 = b * rho
    #             x1 = int(x0 + 1000 * (-b))
    #             y1 = int(y0 + 1000 * (a))
    #             x2 = int(x0 - 1000 * (-b))
    #             y2 = int(y0 - 1000 * (a))
    #             cv2.line(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 1)
    #     
    #     cv2.putText(debug_img, f"Skew: {final_angle:.1f}°", (10, 30),
    #                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    #     show_image(debug_img, "hough_lines_skew_detection")
    
    return final_angle

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
