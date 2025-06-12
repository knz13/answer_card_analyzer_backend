# Answer Card Analyzer Backend

A distributed system for automated analysis of answer sheets (gabaritos) using advanced computer vision techniques. The system uses OpenCV's Hough Circle Transform with intelligent parameter optimization to detect and analyze filled circles on answer sheets.

## 🏗️ Architecture

The system consists of two main components working together:

### 1. **Relay Server** (`main_http.py`)
- **Role**: Central coordination hub
- **Functions**:
  - Receives requests from frontend applications
  - Manages WebSocket connections with processing computers
  - Distributes workload across available processing computers
  - Handles file transfers and progress tracking
  - Provides real-time status updates

### 2. **Processing Computer** (`main_processing_computer.py`)
- **Role**: Computational worker node
- **Functions**:
  - Connects to the relay server as an internal client
  - Performs intensive image processing tasks
  - Executes circle detection algorithms
  - Handles PDF to image conversion
  - Reports progress and results back to relay server

## ✨ Key Features

### Advanced Circle Detection
- **Iterative Parameter Optimization**: Tests multiple parameter combinations to find optimal circle detection settings
- **Quality Scoring System**: Evaluates detected circles based on:
  - Circle count accuracy
  - Radius consistency
  - Overlap penalties
  - Grid pattern rewards
  - Boundary compliance
- **Consensus Recovery**: Combines results from multiple parameter combinations for enhanced accuracy
- **Multi-stage Filtering**: 
  - Bounds filtering (removes circles outside image boundaries)
  - Grid outlier removal (ensures proper grid patterns)
  - Overlap elimination (removes duplicate detections)

### Multi-Page Processing
- **PDF Support**: Automatic conversion of PDF documents to individual page images
- **Progress Tracking**: Real-time progress updates with page-by-page status
- **Batch Processing**: Efficient handling of multi-page answer sheets

### Distributed Processing
- **Horizontal Scaling**: Add multiple processing computers to handle larger workloads
- **Load Balancing**: Automatic distribution of tasks across available processors
- **Fault Tolerance**: Graceful handling of processing computer failures

## 📋 Requirements

### System Dependencies
```bash
# Image processing libraries
opencv-python>=4.8.0
Pillow>=9.0.0
numpy>=1.24.0

# PDF processing
pdf2image>=1.16.0
pymupdf>=1.22.0

# Web framework and WebSocket support
fastapi>=0.100.0
hypercorn>=0.14.0
websockets>=11.0.0

# System monitoring
psutil>=5.9.0

# Additional utilities
starlette>=0.27.0
```

### Installation
```bash
pip install -r requirements.txt
```

## 🚀 Quick Start

### 1. Start the Relay Server
```bash
python main_http.py
```
The relay server will start on:
- **Development**: `http://localhost:8000`
- **Production**: `http://0.0.0.0:8080`

### 2. Start Processing Computer(s)
```bash
python main_processing_computer.py
```
Processing computers will automatically connect to the relay server and register as available workers.

### 3. Monitor System Status
Visit the relay server URL in your browser to see:
- Connected clients
- Active processing computers
- Current job status
- System health metrics

## 🔧 Configuration

### Environment Settings
The system automatically detects the environment:
- **Development**: Connects to `ws://localhost:8000`
- **Production**: Connects to `wss://orca-app-h5tlv.ondigitalocean.app`

### Circle Detection Parameters
Key parameters can be tuned in `find_circles.py`:

```python
# Parameter ranges tested during optimization
dp_values = [1, 1.2]                    # Accumulator resolution
param1_values = [0.4]                   # Upper threshold for edge detection
param2_values = [2, 5, 9]               # Accumulator threshold
threshold_values = [220, 224, 228, 233, 237, 243]  # Binary threshold values
```

### Memory Management
Processing computers include automatic memory monitoring:
```python
MEMORY_THRESHOLD_PERCENT = 90  # Restart when memory usage exceeds 90%
```

## 📡 API Endpoints

### POST `/read_to_images`
Converts PDF documents to individual page images.

**Parameters:**
- `file`: PDF file (multipart/form-data)
- `task_id`: Unique task identifier
- `socket_id`: WebSocket client identifier

**Response:**
```json
{
  "status": "completed_task",
  "data": {
    "images": ["image1_id", "image2_id", ...],
    "files": {
      "image1_id": "base64_encoded_image_data",
      "image2_id": "base64_encoded_image_data"
    }
  }
}
```

### POST `/find_circles`
Analyzes images to detect and classify filled circles.

**Parameters:**
- `file`: Image file or PDF (multipart/form-data)
- `task_id`: Unique task identifier
- `socket_id`: WebSocket client identifier
- `data`: JSON configuration object

**Configuration Object:**
```json
{
  "boxes": [
    {
      "name": "question_section_1",
      "rect": {"x": 0.1, "y": 0.2, "width": 0.8, "height": 0.3},
      "rect_type": "MATRICULA"
    }
  ],
  "circle_size": 0.01,
  "darkness_threshold": 0.7,
  "use_fallback_method": false
}
```

**Response:**
```json
{
  "status": "completed_task",
  "data": {
    "circles": {
      "page1_id": {
        "question_section_1": [
          {
            "center_x": 0.25,
            "center_y": 0.35,
            "radius": 0.01,
            "filled": true,
            "id": "circle_unique_id"
          }
        ]
      }
    }
  }
}
```

## 🔍 Circle Detection Process

### 1. Image Preprocessing
- Resize to standard width (4000px)
- Apply Gaussian blur for noise reduction
- Convert to grayscale

### 2. Parameter Optimization
- Test multiple threshold values (220-243)
- Vary accumulator resolution (dp: 1.0-1.2)
- Adjust detection sensitivity (param2: 2-9)
- Score each combination using quality metrics

### 3. Quality Evaluation
Each detected circle set receives a quality score based on:
- **Count Score (15%)**: Proximity to expected number of circles
- **Radius Consistency (10%)**: Uniformity of detected circle sizes
- **Overlap Penalty (25%)**: Penalizes overlapping circles
- **Boundary Penalty (20%)**: Penalizes circles outside image bounds
- **Grid Pattern Reward (25%)**: Rewards proper row/column alignment
- **Spacing Consistency (5%)**: Rewards uniform circle spacing

### 4. Consensus Recovery
- Analyze top-performing parameter combinations
- Group circles by location (15px tolerance)
- Recover frequently detected circles missed by best single result
- Average circle parameters for improved accuracy

### 5. Multi-stage Filtering
1. **Bounds Filtering**: Remove circles >20% outside image boundaries
2. **Grid Outlier Removal**: Keep only circles fitting row/column patterns
3. **Overlap Removal**: Eliminate duplicate circles (>50% overlap)

## 📊 Progress Tracking

The system provides detailed progress updates:

```
Processing 3 pages for circle detection...

[Page 1/3] Processing image: page1.jpg
Starting page analysis...
[Page 1/3] [Rectangle1 1/2] Starting circle detection optimization...
[Page 1/3] [Rectangle1 1/2] Testing 15/72 (20.8%)
Best: 0.847 | dp=1, param1=0.4, param2=5, threshold=237
[Page 1/3] [Rectangle1 1/2] 🎯 NEW BEST!
Score: 0.892, Circles: 24 | Progress: 67.3%
[Page 1/3] [Rectangle1 1/2] Parameter testing complete!
Final score: 0.892 | Applying consensus recovery...
[Page 1/3] [Rectangle1 1/2] ✨ Analysis complete!
Final result: 18 circles detected
(bounds + outliers + overlaps filtered)

[Page 1/3] ✅ Page 1 complete! (1/3)
Found 18 total circles across 2 regions

🎉 All 3 pages processed!
Total circles found: 59 across all pages
```

## 🐛 Debugging

### Enable Debug Mode
```python
Utils.set_debug(True)
```

Debug mode provides:
- Detailed logging of detection parameters
- Visual circle overlays on processed images
- Step-by-step filtering results
- Quality score breakdowns

### Common Issues

**No circles detected:**
- Check image quality and contrast
- Verify rectangle coordinates (0-1 normalized)
- Adjust `darkness_threshold` parameter
- Ensure circles are within size limits

**Too many false positives:**
- Increase `darkness_threshold`
- Reduce parameter ranges
- Enable stricter grid filtering

**Missing circles:**
- Lower `darkness_threshold`
- Expand parameter ranges
- Check consensus recovery settings

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For issues and questions:
1. Check the debug logs
2. Verify system requirements
3. Review configuration parameters
4. Contact the development team

---

**Note**: This system is designed for educational institutions and testing centers that need to process large volumes of answer sheets efficiently and accurately. 