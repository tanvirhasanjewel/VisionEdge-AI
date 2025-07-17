import streamlit as st
import warnings
import time
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
from ultralytics import YOLO

from config import *
from utils import logger, log_execution_time, validate_image, cleanup_cache, setup_logging

# Setup logging
setup_logging()

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Set Streamlit page config
st.set_page_config(page_title="VisionEdge AI - Detect with Intelligence App", layout="wide")

@log_execution_time
def apply_edge_detection(method: str, image: np.ndarray, params: dict) -> np.ndarray:
    try:
        if method == "Canny":
            return cv2.Canny(image, params['threshold1'], params['threshold2'])
        elif method == "Sobel":
            sobelx = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=params['kernel_size'])
            sobely = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=params['kernel_size'])
            edges = cv2.magnitude(sobelx, sobely)
        elif method == "Laplacian":
            edges = cv2.Laplacian(image, cv2.CV_64F, ksize=params['laplacian_kernel'])
        return cv2.normalize(edges, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    except Exception as e:
        logger.error(f"Edge detection failed: {str(e)}")
        raise RuntimeError(f"Edge detection failed: {str(e)}")

@log_execution_time
def detect_objects(model, image: np.ndarray, selected_classes: list):
    try:
        start_time = time.time()
        results = model(image)
        detections = []
        counts = {}
        viz_image = image.copy()

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]
                if selected_classes and class_name not in selected_classes:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cv2.rectangle(viz_image, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(viz_image, f"{class_name} {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                detections.append({"class": class_name, "confidence": conf, "bbox": [x1, y1, x2, y2]})
                counts[class_name] = counts.get(class_name, 0) + 1

        return viz_image, detections, counts, time.time()-start_time
    except Exception as e:
        logger.error(f"Object detection failed: {str(e)}")
        raise RuntimeError(f"Object detection failed: {str(e)}")

@log_execution_time
def generate_heatmap(edges: np.ndarray) -> np.ndarray:
    try:
        return cv2.applyColorMap(edges, cv2.COLORMAP_JET)
    except Exception as e:
        logger.error(f"Heatmap generation failed: {str(e)}")
        raise RuntimeError(f"Heatmap generation failed: {str(e)}")

def apply_theme(high_contrast):
    if high_contrast:
        st.markdown("""
            <style>
            body, .main {background-color: #fff; color: #000;}
            .stSidebar {background-color: #f1f1f1;}
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
            body, .main {background-color: #000; color: #fff;}
            .stSidebar {background-color: #111;}
            </style>
        """, unsafe_allow_html=True)

def load_yolo_model():
    model_path = Path(MODEL_PATH)
    if not model_path.exists():
        raise FileNotFoundError(f"YOLO model not found at {MODEL_PATH}")
    return YOLO(model_path)

def main():
    st.title("VisionEdge AI - Detect with Intelligence App")

    high_contrast = st.sidebar.checkbox("High Contrast Mode")
    apply_theme(high_contrast)

    try:
        model = load_yolo_model()
    except Exception as e:
        st.error(str(e))
        return

    uploaded_file = st.file_uploader("Upload an Image", type=SUPPORTED_FORMATS)
    if uploaded_file:
        valid, message = validate_image(uploaded_file)
        if not valid:
            st.error(message)
            return

        img = Image.open(uploaded_file)
        img_rgb = np.array(img.convert("RGB"))
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

        edge_method = st.selectbox("Edge Detection Method", EDGE_METHODS)
        edge_params = {}
        if edge_method == "Canny":
            edge_params['threshold1'] = st.slider("Canny Threshold 1", 0, 500, 100)
            edge_params['threshold2'] = st.slider("Canny Threshold 2", 0, 500, 200)
        elif edge_method == "Sobel":
            edge_params['kernel_size'] = st.slider("Sobel Kernel Size", 3, 15, 3, step=2)
        elif edge_method == "Laplacian":
            edge_params['laplacian_kernel'] = st.slider("Laplacian Kernel Size", 3, 15, 3, step=2)

        selected_classes = st.multiselect("YOLO Classes to Detect", list(model.names.values()), default=list(model.names.values())[:DEFAULT_CLASSES_TO_SHOW])

        processed_img = apply_edge_detection(edge_method, img_gray, edge_params)
        heatmap = generate_heatmap(processed_img)
        yolo_image, detections, counts, _ = detect_objects(model, img_rgb, selected_classes)

        col1, col2 = st.columns(2)
        with col1:
            st.image(img_rgb, caption="Original Image", use_column_width=True)
            st.image(processed_img, caption=f"{edge_method} Edge Detection", use_column_width=True)
        with col2:
            st.image(yolo_image, caption="YOLO Detection", use_column_width=True)
            st.image(heatmap, caption="Heatmap", use_column_width=True)

        if detections:
            st.subheader("Detections")
            st.dataframe(pd.DataFrame(detections))

if __name__ == "__main__":
    main()
