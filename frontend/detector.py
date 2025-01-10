import os
import torch
import numpy as np
from pathlib import Path
from time import time
from utils.general import (LOGGER, Profile, check_file, check_img_size, check_imshow, check_requirements, colorstr, cv2,
                           increment_path, non_max_suppression, print_args, scale_boxes, strip_optimizer, xyxy2xywh)
from utils.plots import Annotator, colors, save_one_box
from models.common import DetectMultiBackend


class TrafficSignDetector:
    def __init__(self, model_path="D:/CS/MachineLearning/TrafficDetection/yolov5-master/runs/train/exp4/weights/best.pt", imgsz=(640, 640), device='cpu'):
        self.model = DetectMultiBackend(model_path, device=torch.device(device))
        self.imgsz = imgsz    
        
            
    def detect(self, frame):
        """
        Detect traffic signs in the image

        Args:
            frame: Image frame in OpenCV format

        Returns:
            list: List of detection results, each element contains:
            - bbox: Bounding box coordinates [x1, y1, x2, y2]
            - type: Type of traffic sign
            - confidence: Confidence probability
            - distance: Estimated distance
        """

        import random
        import time

        time.sleep(0.3)

        detections = []
        
        self.model.warmup(imgsz=(1, 3, *self.imgsz))  # warmup
        seen, windows, dt = 0, [], (Profile(), Profile(), Profile())
        
        with dt[0]:
            im = torch.from_numpy(frame).permute(2, 0, 1).to(self.model.device)  # HWC -> CHW
            im = im.half() if self.model.fp16 else im.float()  # uint8 to fp16/32
            im /= 255  # 0 - 255 to 0.0 - 1.0
            if len(im.shape) == 3:
                im = im[None]  # expand for batch dim

        # Inference
        with dt[1]:
            pred = self.model(im, augment=False, visualize=None)

        # NMS
        with dt[2]:
            conf_thres = 0.25
            iou_thres = 0.45
            classes = None
            agnostic_nms = False
            max_det = 1000
            pred = non_max_suppression(pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det)
        
        print(pred)
        
        for i, det in enumerate(pred):  # per image
            seen += 1
            im0 = frame.copy()
            # annotator = Annotator(im0, line_width=3, example=str(self.model.names))
            
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()
                for *xyxy, conf, cls in reversed(det):
                    c = int(cls)  # integer class
                    label = self.model.names[c]
                    # annotator.box_label(xyxy, label, color=colors(c, True))
                    # im0 = annotator.result()
                    
                    distance = self.estimate_distance(xyxy)
                    detections.append({
                    "bbox": xyxy,
                    "type": label,
                    "confidence": conf,
                    "distance": round(distance, 2),
                    })
        return detections

    def estimate_distance(self, bbox):
        # TODO: hyperparameter needed to be tuned

        # method 1: pnp
        camera_matrix = np.array([[1000, 0, 320], [0, 1000, 240], [0, 0, 1]])
        dist_coeffs = np.zeros((4, 1))
        real_height = 0.5
        real_width = 0.5
        focal_length = camera_matrix[0, 0]
        img_height = bbox[3] - bbox[1]
        img_width = bbox[2] - bbox[0]
        distance_pnp = (real_height * focal_length) / img_height

        # method 2: area
        img_area = img_height * img_width
        unit_distance = 10
        distance_area = unit_distance / img_area

        weight_pnp = 0.7
        weight_area = 0.3

        distance = weight_pnp * distance_pnp + weight_area * distance_area
        return float(distance)

