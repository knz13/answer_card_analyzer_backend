import random
import cv2
import numpy as np
from sklearn.cluster import MeanShift
from utils import Utils, show_image

def angle_diff(a, b):
    """Minimal difference between two angles"""
    diff = a - b
    return np.arctan2(np.sin(diff), np.cos(diff))

def get_arc_support_lss(edges, direction, magnitude, mag_thresh=20, angle_interval=np.deg2rad(2.25)):
    h, w = edges.shape
    visited = np.zeros_like(edges, dtype=bool)
    arc_lss = []

    def region_grow(y, x):
        """Simple region growing based on gradient direction coherence"""
        stack = [(y, x)]
        points = []
        base_angle = direction[y, x]

        while stack:
            cy, cx = stack.pop()
            if visited[cy, cx]:
                continue
            if magnitude[cy, cx] < mag_thresh or edges[cy, cx] == 0:
                continue
            visited[cy, cx] = True
            points.append((cy, cx))
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                        ang_diff = abs(angle_diff(direction[ny, nx], base_angle))
                        if ang_diff < angle_interval:
                            stack.append((ny, nx))
        return points

    for y in range(h):
        for x in range(w):
            if edges[y, x] and not visited[y, x] and magnitude[y, x] > mag_thresh:
                region = region_grow(y, x)
                if len(region) >= 10:  # avoid noise
                    pts = np.array([(x_, y_) for y_, x_ in region], dtype=np.float32)
                    mean = np.mean(pts, axis=0)
                    cov = np.cov(pts.T)
                    eigvals, eigvecs = np.linalg.eigh(cov)
                    principal_dir = eigvecs[:, np.argmax(eigvals)]
                    arc_lss.append({
                        'points': pts,
                        'center': mean,
                        'direction': principal_dir,
                        'angle_variation': direction[region[-1][0], region[-1][1]] - direction[region[0][0], region[0][1]],
                        'polarity': np.sign(direction[region[-1][0], region[-1][1]] - direction[region[0][0], region[0][1]])
                    })
    return arc_lss

def intersect_lines(p1, d1, p2, d2):
    """Find intersection of two lines given a point and direction each"""
    A = np.array([d1, -d2]).T
    if np.linalg.matrix_rank(A) < 2:
        return None  # parallel lines
    b = p2 - p1
    t = np.linalg.lstsq(A, b, rcond=None)[0][0]
    return p1 + d1 * t

def generate_circle_candidates(arc_lss, eps_radius_ratio=0.1):
    candidates = []
    
    for i in range(len(arc_lss)):
        for j in range(i+1, len(arc_lss)):
            l1 = arc_lss[i]
            l2 = arc_lss[j]
            
            # Polarity must match
            if l1['polarity'] != l2['polarity']:
                continue
                
            # Get directions
            dir1 = l1['direction']
            dir2 = l2['direction']
            mid1 = l1['center']
            mid2 = l2['center']
            
            # Normal vectors (perpendicular to LS)
            normal1 = np.array([-dir1[1], dir1[0]])
            normal2 = np.array([-dir2[1], dir2[0]])
            
            center = intersect_lines(mid1, normal1, mid2, normal2)
            if center is None:
                continue
                
            # Estimate radii
            dist1 = np.mean(np.linalg.norm(l1['points'] - center, axis=1))
            dist2 = np.mean(np.linalg.norm(l2['points'] - center, axis=1))
            if abs(dist1 - dist2) > eps_radius_ratio * max(dist1, dist2):
                continue
                
            radius = (dist1 + dist2) / 2
            candidates.append((center, radius, l1, l2))
            
    return candidates

def cluster_circles(candidates, bandwidth=10):
    if not candidates:
        return []
        
    centers = np.array([np.hstack([c[0], c[1]]) for c in candidates])  # [x, y, r]
    ms = MeanShift(bandwidth=bandwidth, bin_seeding=True)
    ms.fit(centers)
    clustered = []
    
    for label in np.unique(ms.labels_):
        group = centers[ms.labels_ == label]
        mean = np.mean(group, axis=0)
        clustered.append((mean[:2], mean[2]))  # (center, radius)
        
    return clustered

def fit_circle_least_squares(points):
    A = np.hstack([2 * points, np.ones((points.shape[0], 1))])
    b = np.sum(points**2, axis=1)
    sol, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    center = sol[:2]
    radius = np.sqrt(sol[2] + center @ center)
    return center, radius

def get_circle_inliers(edge_img, center, radius, dist_thresh=2.0):
    y_idxs, x_idxs = np.nonzero(edge_img)
    pts = np.stack([x_idxs, y_idxs], axis=1).astype(np.float32)
    dists = np.abs(np.linalg.norm(pts - center, axis=1) - radius)
    inliers = pts[dists < dist_thresh]
    return inliers

def refine_circles(edge_img, clustered, dist_thresh=2.0, min_inliers=30, min_coverage_deg=165):
    refined = []
    
    for center, radius in clustered:
        inliers = get_circle_inliers(edge_img, center, radius, dist_thresh)
        if len(inliers) < min_inliers:
            continue
            
        # First fit
        center1, radius1 = fit_circle_least_squares(inliers)
        inliers2 = get_circle_inliers(edge_img, center1, radius1, dist_thresh)
        
        # Second fit
        center2, radius2 = fit_circle_least_squares(inliers2)
        
        # Validate angular coverage
        angles = np.arctan2(inliers2[:, 1] - center2[1], inliers2[:, 0] - center2[0])
        angle_span = np.rad2deg(np.ptp(np.unwrap(angles)))
        if angle_span >= min_coverage_deg:
            refined.append((center2, radius2))
            
    return refined

async def find_circles_arc_support(image_path, rectangle, rectangle_type, darkness_threshold=180/255, img=None, on_progress=None, circle_size=None):
    """Find circles using Arc-Support Line Segments method"""
    if img is None:
        img = cv2.imread(image_path)

    # make image 4000 width
    image_new_width = 4000
    width_ratio = image_new_width / img.shape[1]
    img = cv2.resize(img, fx=width_ratio, fy=width_ratio, dsize=(0, 0))

    old_x, old_y, width, height = rectangle.values()
    
    if old_x > 1 or old_y > 1 or width > 1 or height > 1 or old_x < 0 or old_y < 0 or width < 0 or height < 0:
        raise ValueError("The rectangle values must be between 0 and 1.")

    # transform to absolute
    x = int(old_x * img.shape[1])
    y = int(old_y * img.shape[0])
    width = int(width * img.shape[1])
    height = int(height * img.shape[0])

    # crop image on rectangle
    crop_img = img[y:y+height, x:x+width]
    
    if on_progress is not None:
        await on_progress("Computing gradients and edges...")
    
    # Convert to grayscale
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    
    # Apply threshold at 200
    _, binary = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
    
    # Use the binary image for gradient computation
    grad_x = cv2.Sobel(binary, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(binary, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(grad_x**2 + grad_y**2)
    direction = np.arctan2(grad_y, grad_x)
    
    # Get edges with adjusted Canny parameters
    edges = cv2.Canny(binary, 100, 200)
    
    if Utils.is_debug():
        Utils.log_info("Showing binary and edges")
        show_image(binary, "Binary")
        show_image(edges, "Edges")
    
    if on_progress is not None:
        await on_progress("Extracting arc-support line segments...")
    
    # Get arc-support line segments
    arc_lss = get_arc_support_lss(edges, direction, magnitude)
    
    if on_progress is not None:
        await on_progress("Generating circle candidates...")
    
    # Generate circle candidates
    candidates = generate_circle_candidates(arc_lss)
    
    if on_progress is not None:
        await on_progress("Clustering and refining circles...")
    
    # Cluster and refine
    clustered = cluster_circles(candidates)
    final_circles = refine_circles(edges, clustered)
    
    output_circles = []
    for center, radius in final_circles:
        # Check if circle is filled using the binary image
        mask = np.zeros_like(binary)
        cv2.circle(mask, tuple(map(int, center)), int(radius), 255, -1)
        mean_intensity = cv2.mean(binary, mask=mask)[0]
        filled = mean_intensity < darkness_threshold * 255
        
        # Adjust coordinates back to original image
        center_x = (center[0] + x) / width_ratio
        center_y = (center[1] + y) / width_ratio
        radius = radius / width_ratio
        
        output_circles.append({
            "center_x": float(center_x),
            "center_y": float(center_y),
            "radius": float(radius),
            "filled": filled,
            "id": random.randbytes(10).hex()
        })
    
    return output_circles 