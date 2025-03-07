import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

from albumentations.augmentations.geometric import functional as FGeometric
from albumentations.core.bbox_utils import union_of_bboxes
from albumentations.core.transforms_interface import DualTransform, to_tuple
from albumentations.core.types import BoxInternalType, KeypointInternalType, ScaleFloatType

from . import functional as F

__all__ = [
    "RandomCrop",
    "CenterCrop",
    "Crop",
    "CropNonEmptyMaskIfExists",
    "RandomSizedCrop",
    "RandomResizedCrop",
    "RandomCropNearBBox",
    "RandomSizedBBoxSafeCrop",
    "CropAndPad",
    "RandomCropFromBorders",
    "BBoxSafeRandomCrop",
]

TWO = 2
THREE = 3


class RandomCrop(DualTransform):
    """Crop a random part of the input.

    Args:
    ----
        height: height of the crop.
        width: width of the crop.
        p: probability of applying the transform. Default: 1.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    """

    def __init__(self, height: int, width: int, always_apply: bool = False, p: float = 1.0):
        super().__init__(always_apply, p)
        self.height = height
        self.width = width

    def apply(self, img: np.ndarray, h_start: int = 0, w_start: int = 0, **params: Any) -> np.ndarray:
        return F.random_crop(img, self.height, self.width, h_start, w_start)

    def get_params(self) -> Dict[str, float]:
        return {"h_start": random.random(), "w_start": random.random()}

    def apply_to_bbox(self, bbox: BoxInternalType, **params: Any) -> BoxInternalType:
        return F.bbox_random_crop(bbox, self.height, self.width, **params)

    def apply_to_keypoint(self, keypoint: KeypointInternalType, **params: Any) -> KeypointInternalType:
        return F.keypoint_random_crop(keypoint, self.height, self.width, **params)

    def get_transform_init_args_names(self) -> Tuple[str, str]:
        return ("height", "width")


class CenterCrop(DualTransform):
    """Crop the central part of the input.

    Args:
    ----
        height: height of the crop.
        width: width of the crop.
        p: probability of applying the transform. Default: 1.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    Note:
    ----
        It is recommended to use uint8 images as input.
        Otherwise the operation will require internal conversion
        float32 -> uint8 -> float32 that causes worse performance.

    """

    def __init__(self, height: int, width: int, always_apply: bool = False, p: float = 1.0):
        super().__init__(always_apply, p)
        self.height = height
        self.width = width

    def apply(self, img: np.ndarray, **params: Any) -> np.ndarray:
        return F.center_crop(img, self.height, self.width)

    def apply_to_bbox(self, bbox: BoxInternalType, **params: Any) -> BoxInternalType:
        return F.bbox_center_crop(bbox, self.height, self.width, **params)

    def apply_to_keypoint(self, keypoint: KeypointInternalType, **params: Any) -> KeypointInternalType:
        return F.keypoint_center_crop(keypoint, self.height, self.width, **params)

    def get_transform_init_args_names(self) -> Tuple[str, str]:
        return ("height", "width")


class Crop(DualTransform):
    """Crop region from image.

    Args:
    ----
        x_min: Minimum upper left x coordinate.
        y_min: Minimum upper left y coordinate.
        x_max: Maximum lower right x coordinate.
        y_max: Maximum lower right y coordinate.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    """

    def __init__(
        self,
        x_min: int = 0,
        y_min: int = 0,
        x_max: int = 1024,
        y_max: int = 1024,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(always_apply, p)
        self.x_min = x_min
        self.y_min = y_min
        self.x_max = x_max
        self.y_max = y_max

    def apply(self, img: np.ndarray, **params: Any) -> np.ndarray:
        return F.crop(img, x_min=self.x_min, y_min=self.y_min, x_max=self.x_max, y_max=self.y_max)

    def apply_to_bbox(self, bbox: BoxInternalType, **params: Any) -> BoxInternalType:
        return F.bbox_crop(bbox, x_min=self.x_min, y_min=self.y_min, x_max=self.x_max, y_max=self.y_max, **params)

    def apply_to_keypoint(self, keypoint: KeypointInternalType, **params: Any) -> KeypointInternalType:
        return F.crop_keypoint_by_coords(keypoint, crop_coords=(self.x_min, self.y_min, self.x_max, self.y_max))

    def get_transform_init_args_names(self) -> Tuple[str, str, str, str]:
        return ("x_min", "y_min", "x_max", "y_max")


class CropNonEmptyMaskIfExists(DualTransform):
    """Crop area with mask if mask is non-empty, else make random crop.

    Args:
    ----
        height: vertical size of crop in pixels
        width: horizontal size of crop in pixels
        ignore_values (list of int): values to ignore in mask, `0` values are always ignored
            (e.g. if background value is 5 set `ignore_values=[5]` to ignore)
        ignore_channels (list of int): channels to ignore in mask
            (e.g. if background is a first channel set `ignore_channels=[0]` to ignore)
        p: probability of applying the transform. Default: 1.0.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    """

    def __init__(
        self,
        height: int,
        width: int,
        ignore_values: Optional[List[int]] = None,
        ignore_channels: Optional[List[int]] = None,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(always_apply, p)

        if ignore_values is not None and not isinstance(ignore_values, list):
            raise ValueError(f"Expected `ignore_values` of type `list`, got `{type(ignore_values)}`")
        if ignore_channels is not None and not isinstance(ignore_channels, list):
            raise ValueError(f"Expected `ignore_channels` of type `list`, got `{type(ignore_channels)}`")

        self.height = height
        self.width = width
        self.ignore_values = ignore_values
        self.ignore_channels = ignore_channels

    def apply(
        self, img: np.ndarray, x_min: int = 0, x_max: int = 0, y_min: int = 0, y_max: int = 0, **params: Any
    ) -> np.ndarray:
        return F.crop(img, x_min, y_min, x_max, y_max)

    def apply_to_bbox(
        self, bbox: BoxInternalType, x_min: int = 0, x_max: int = 0, y_min: int = 0, y_max: int = 0, **params: Any
    ) -> BoxInternalType:
        return F.bbox_crop(
            bbox, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max, rows=params["rows"], cols=params["cols"]
        )

    def apply_to_keypoint(
        self,
        keypoint: KeypointInternalType,
        x_min: int = 0,
        x_max: int = 0,
        y_min: int = 0,
        y_max: int = 0,
        **params: Any,
    ) -> KeypointInternalType:
        return F.crop_keypoint_by_coords(keypoint, crop_coords=(x_min, y_min, x_max, y_max))

    def _preprocess_mask(self, mask: np.ndarray) -> np.ndarray:
        mask_height, mask_width = mask.shape[:2]

        if self.ignore_values is not None:
            ignore_values_np = np.array(self.ignore_values)
            mask = np.where(np.isin(mask, ignore_values_np), 0, mask)

        if mask.ndim == THREE and self.ignore_channels is not None:
            target_channels = np.array([ch for ch in range(mask.shape[-1]) if ch not in self.ignore_channels])
            mask = np.take(mask, target_channels, axis=-1)

        if self.height > mask_height or self.width > mask_width:
            raise ValueError(
                f"Crop size ({self.height},{self.width}) is larger than image ({mask_height},{mask_width})"
            )

        return mask

    def update_params(self, params: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        super().update_params(params, **kwargs)
        if "mask" in kwargs:
            mask = self._preprocess_mask(kwargs["mask"])
        elif "masks" in kwargs and len(kwargs["masks"]):
            masks = kwargs["masks"]
            mask = self._preprocess_mask(np.copy(masks[0]))  # need copy as we perform in-place mod afterwards
            for m in masks[1:]:
                mask |= self._preprocess_mask(m)
        else:
            msg = "Can not find mask for CropNonEmptyMaskIfExists"
            raise RuntimeError(msg)

        mask_height, mask_width = mask.shape[:2]

        if mask.any():
            mask = mask.sum(axis=-1) if mask.ndim == THREE else mask
            non_zero_yx = np.argwhere(mask)
            y, x = random.choice(non_zero_yx)
            x_min = x - random.randint(0, self.width - 1)
            y_min = y - random.randint(0, self.height - 1)
            x_min = np.clip(x_min, 0, mask_width - self.width)
            y_min = np.clip(y_min, 0, mask_height - self.height)
        else:
            x_min = random.randint(0, mask_width - self.width)
            y_min = random.randint(0, mask_height - self.height)

        x_max = x_min + self.width
        y_max = y_min + self.height

        params.update({"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max})
        return params

    def get_transform_init_args_names(self) -> Tuple[str, str, str, str]:
        return ("height", "width", "ignore_values", "ignore_channels")


class _BaseRandomSizedCrop(DualTransform):
    # Base class for RandomSizedCrop and RandomResizedCrop

    def __init__(
        self, height: int, width: int, interpolation: int = cv2.INTER_LINEAR, always_apply: bool = False, p: float = 1.0
    ):
        super().__init__(always_apply, p)
        self.height = height
        self.width = width
        self.interpolation = interpolation

    def apply(
        self,
        img: np.ndarray,
        crop_height: int = 0,
        crop_width: int = 0,
        h_start: int = 0,
        w_start: int = 0,
        interpolation: int = cv2.INTER_LINEAR,
        **params: Any,
    ) -> np.ndarray:
        crop = F.random_crop(img, crop_height, crop_width, h_start, w_start)
        return FGeometric.resize(crop, self.height, self.width, interpolation)

    def apply_to_bbox(
        self,
        bbox: BoxInternalType,
        crop_height: int = 0,
        crop_width: int = 0,
        h_start: int = 0,
        w_start: int = 0,
        rows: int = 0,
        cols: int = 0,
        **params: Any,
    ) -> BoxInternalType:
        return F.bbox_random_crop(bbox, crop_height, crop_width, h_start, w_start, rows, cols)

    def apply_to_keypoint(
        self,
        keypoint: KeypointInternalType,
        crop_height: int = 0,
        crop_width: int = 0,
        h_start: int = 0,
        w_start: int = 0,
        rows: int = 0,
        cols: int = 0,
        **params: Any,
    ) -> KeypointInternalType:
        keypoint = F.keypoint_random_crop(keypoint, crop_height, crop_width, h_start, w_start, rows, cols)
        scale_x = self.width / crop_width
        scale_y = self.height / crop_height
        return FGeometric.keypoint_scale(keypoint, scale_x, scale_y)


class RandomSizedCrop(_BaseRandomSizedCrop):
    """Crop a random part of the input and rescale it to some size.

    Args:
    ----
        min_max_height ((int, int)): crop size limits.
        height (int): height after crop and resize.
        width (int): width after crop and resize.
        w2h_ratio (float): aspect ratio of crop.
        interpolation (OpenCV flag): flag that is used to specify the interpolation algorithm. Should be one of:
            cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC, cv2.INTER_AREA, cv2.INTER_LANCZOS4.
            Default: cv2.INTER_LINEAR.
        p (float): probability of applying the transform. Default: 1.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    """

    def __init__(
        self,
        min_max_height: Tuple[int, int],
        height: int,
        width: int,
        w2h_ratio: float = 1.0,
        interpolation: int = cv2.INTER_LINEAR,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(height=height, width=width, interpolation=interpolation, always_apply=always_apply, p=p)
        self.min_max_height = min_max_height
        self.w2h_ratio = w2h_ratio

    def get_params(self) -> Dict[str, Union[int, float]]:
        crop_height = random.randint(self.min_max_height[0], self.min_max_height[1])
        return {
            "h_start": random.random(),
            "w_start": random.random(),
            "crop_height": crop_height,
            "crop_width": int(crop_height * self.w2h_ratio),
        }

    def get_transform_init_args_names(self) -> Tuple[str, str, str, str, str]:
        return "min_max_height", "height", "width", "w2h_ratio", "interpolation"


class RandomResizedCrop(_BaseRandomSizedCrop):
    """Torchvision's variant of crop a random part of the input and rescale it to some size.

    Args:
    ----
        height (int): height after crop and resize.
        width (int): width after crop and resize.
        scale ((float, float)): range of size of the origin size cropped
        ratio ((float, float)): range of aspect ratio of the origin aspect ratio cropped
        interpolation (OpenCV flag): flag that is used to specify the interpolation algorithm. Should be one of:
            cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC, cv2.INTER_AREA, cv2.INTER_LANCZOS4.
            Default: cv2.INTER_LINEAR.
        p (float): probability of applying the transform. Default: 1.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    """

    def __init__(
        self,
        height: int,
        width: int,
        scale: Tuple[float, float] = (0.08, 1.0),
        ratio: Tuple[float, float] = (0.75, 1.3333333333333333),
        interpolation: int = cv2.INTER_LINEAR,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(height=height, width=width, interpolation=interpolation, always_apply=always_apply, p=p)
        self.scale = scale
        self.ratio = ratio

    def get_params_dependent_on_targets(self, params: Dict[str, Any]) -> Dict[str, Union[int, float]]:
        img = params["image"]
        area = img.shape[0] * img.shape[1]

        for _ in range(10):
            target_area = random.uniform(*self.scale) * area
            log_ratio = (math.log(self.ratio[0]), math.log(self.ratio[1]))
            aspect_ratio = math.exp(random.uniform(*log_ratio))

            width = int(round(math.sqrt(target_area * aspect_ratio)))
            height = int(round(math.sqrt(target_area / aspect_ratio)))

            if 0 < width <= img.shape[1] and 0 < height <= img.shape[0]:
                i = random.randint(0, img.shape[0] - height)
                j = random.randint(0, img.shape[1] - width)
                return {
                    "crop_height": height,
                    "crop_width": width,
                    "h_start": i * 1.0 / (img.shape[0] - height + 1e-10),
                    "w_start": j * 1.0 / (img.shape[1] - width + 1e-10),
                }

        # Fallback to central crop
        in_ratio = img.shape[1] / img.shape[0]
        if in_ratio < min(self.ratio):
            width = img.shape[1]
            height = int(round(width / min(self.ratio)))
        elif in_ratio > max(self.ratio):
            height = img.shape[0]
            width = int(round(height * max(self.ratio)))
        else:  # whole image
            width = img.shape[1]
            height = img.shape[0]
        i = (img.shape[0] - height) // 2
        j = (img.shape[1] - width) // 2
        return {
            "crop_height": height,
            "crop_width": width,
            "h_start": i * 1.0 / (img.shape[0] - height + 1e-10),
            "w_start": j * 1.0 / (img.shape[1] - width + 1e-10),
        }

    def get_params(self) -> Dict[str, Any]:
        return {}

    @property
    def targets_as_params(self) -> List[str]:
        return ["image"]

    def get_transform_init_args_names(self) -> Tuple[str, str, str, str, str]:
        return "height", "width", "scale", "ratio", "interpolation"


class RandomCropNearBBox(DualTransform):
    """Crop bbox from image with random shift by x,y coordinates

    Args:
    ----
        max_part_shift (float, (float, float)): Max shift in `height` and `width` dimensions relative
            to `cropping_bbox` dimension.
            If max_part_shift is a single float, the range will be (max_part_shift, max_part_shift).
            Default (0.3, 0.3).
        cropping_box_key (str): Additional target key for cropping box. Default `cropping_bbox`
        p (float): probability of applying the transform. Default: 1.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    Examples:
    --------
        >>> aug = Compose([RandomCropNearBBox(max_part_shift=(0.1, 0.5), cropping_box_key='test_box')],
        >>>              bbox_params=BboxParams("pascal_voc"))
        >>> result = aug(image=image, bboxes=bboxes, test_box=[0, 5, 10, 20])

    """

    def __init__(
        self,
        max_part_shift: ScaleFloatType = (0.3, 0.3),
        cropping_box_key: str = "cropping_bbox",
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(always_apply, p)
        self.max_part_shift = to_tuple(max_part_shift, low=max_part_shift)
        self.cropping_bbox_key = cropping_box_key

        if min(self.max_part_shift) < 0 or max(self.max_part_shift) > 1:
            raise ValueError(f"Invalid max_part_shift. Got: {max_part_shift}")

    def apply(
        self, img: np.ndarray, x_min: int = 0, x_max: int = 0, y_min: int = 0, y_max: int = 0, **params: Any
    ) -> np.ndarray:
        return F.clamping_crop(img, x_min, y_min, x_max, y_max)

    def get_params_dependent_on_targets(self, params: Dict[str, Any]) -> Dict[str, int]:
        bbox = params[self.cropping_bbox_key]
        h_max_shift = round((bbox[3] - bbox[1]) * self.max_part_shift[0])
        w_max_shift = round((bbox[2] - bbox[0]) * self.max_part_shift[1])

        x_min = bbox[0] - random.randint(-w_max_shift, w_max_shift)
        x_max = bbox[2] + random.randint(-w_max_shift, w_max_shift)

        y_min = bbox[1] - random.randint(-h_max_shift, h_max_shift)
        y_max = bbox[3] + random.randint(-h_max_shift, h_max_shift)

        x_min = max(0, x_min)
        y_min = max(0, y_min)

        return {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max}

    def apply_to_bbox(self, bbox: BoxInternalType, **params: Any) -> BoxInternalType:
        return F.bbox_crop(bbox, **params)

    def apply_to_keypoint(
        self,
        keypoint: KeypointInternalType,
        x_min: int = 0,
        x_max: int = 0,
        y_min: int = 0,
        y_max: int = 0,
        **params: Any,
    ) -> KeypointInternalType:
        return F.crop_keypoint_by_coords(keypoint, crop_coords=(x_min, y_min, x_max, y_max))

    @property
    def targets_as_params(self) -> List[str]:
        return [self.cropping_bbox_key]

    def get_transform_init_args_names(self) -> Tuple[str]:
        return ("max_part_shift",)


class BBoxSafeRandomCrop(DualTransform):
    """Crop a random part of the input without loss of bboxes.

    Args:
    ----
        erosion_rate: erosion rate applied on input image height before crop.
        p: probability of applying the transform. Default: 1.
    Targets:
        image, mask, bboxes
    Image types:
        uint8, float32

    """

    def __init__(self, erosion_rate: float = 0.0, always_apply: bool = False, p: float = 1.0):
        super().__init__(always_apply, p)
        self.erosion_rate = erosion_rate

    def apply(
        self,
        img: np.ndarray,
        crop_height: int = 0,
        crop_width: int = 0,
        h_start: int = 0,
        w_start: int = 0,
        **params: Any,
    ) -> np.ndarray:
        return F.random_crop(img, crop_height, crop_width, h_start, w_start)

    def get_params_dependent_on_targets(self, params: Dict[str, Any]) -> Dict[str, Union[int, float]]:
        img_h, img_w = params["image"].shape[:2]
        if len(params["bboxes"]) == 0:  # less likely, this class is for use with bboxes.
            erosive_h = int(img_h * (1.0 - self.erosion_rate))
            crop_height = img_h if erosive_h >= img_h else random.randint(erosive_h, img_h)
            return {
                "h_start": random.random(),
                "w_start": random.random(),
                "crop_height": crop_height,
                "crop_width": int(crop_height * img_w / img_h),
            }
        # get union of all bboxes
        x, y, x2, y2 = union_of_bboxes(
            width=img_w, height=img_h, bboxes=params["bboxes"], erosion_rate=self.erosion_rate
        )
        # find bigger region
        bx, by = x * random.random(), y * random.random()
        bx2, by2 = x2 + (1 - x2) * random.random(), y2 + (1 - y2) * random.random()
        bw, bh = bx2 - bx, by2 - by
        crop_height = img_h if bh >= 1.0 else int(img_h * bh)
        crop_width = img_w if bw >= 1.0 else int(img_w * bw)
        h_start = np.clip(0.0 if bh >= 1.0 else by / (1.0 - bh), 0.0, 1.0)
        w_start = np.clip(0.0 if bw >= 1.0 else bx / (1.0 - bw), 0.0, 1.0)
        return {"h_start": h_start, "w_start": w_start, "crop_height": crop_height, "crop_width": crop_width}

    def apply_to_bbox(
        self,
        bbox: BoxInternalType,
        crop_height: int = 0,
        crop_width: int = 0,
        h_start: int = 0,
        w_start: int = 0,
        rows: int = 0,
        cols: int = 0,
        **params: Any,
    ) -> BoxInternalType:
        return F.bbox_random_crop(bbox, crop_height, crop_width, h_start, w_start, rows, cols)

    @property
    def targets_as_params(self) -> List[str]:
        return ["image", "bboxes"]

    def get_transform_init_args_names(self) -> Tuple[str, ...]:
        return ("erosion_rate",)


class RandomSizedBBoxSafeCrop(BBoxSafeRandomCrop):
    """Crop a random part of the input and rescale it to some size without loss of bboxes.

    Args:
    ----
        height: height after crop and resize.
        width: width after crop and resize.
        erosion_rate: erosion rate applied on input image height before crop.
        interpolation (OpenCV flag): flag that is used to specify the interpolation algorithm. Should be one of:
            cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC, cv2.INTER_AREA, cv2.INTER_LANCZOS4.
            Default: cv2.INTER_LINEAR.
        p (float): probability of applying the transform. Default: 1.
    Targets:
        image, mask, bboxes
    Image types:
        uint8, float32

    """

    def __init__(
        self,
        height: int,
        width: int,
        erosion_rate: float = 0.0,
        interpolation: int = cv2.INTER_LINEAR,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(erosion_rate, always_apply, p)
        self.height = height
        self.width = width
        self.interpolation = interpolation

    def apply(
        self,
        img: np.ndarray,
        crop_height: int = 0,
        crop_width: int = 0,
        h_start: int = 0,
        w_start: int = 0,
        interpolation: int = cv2.INTER_LINEAR,
        **params: Any,
    ) -> np.ndarray:
        crop = F.random_crop(img, crop_height, crop_width, h_start, w_start)
        return FGeometric.resize(crop, self.height, self.width, interpolation)

    def get_transform_init_args_names(self) -> Tuple[str, ...]:
        return (*super().get_transform_init_args_names(), "height", "width", "interpolation")


class CropAndPad(DualTransform):
    """Crop and pad images by pixel amounts or fractions of image sizes.
    Cropping removes pixels at the sides (i.e. extracts a subimage from a given full image).
    Padding adds pixels to the sides (e.g. black pixels).
    This transformation will never crop images below a height or width of ``1``.

    Note:
    ----
        This transformation automatically resizes images back to their original size. To deactivate this, add the
        parameter ``keep_size=False``.

    Args:
    ----
        px (int or tuple):
            The number of pixels to crop (negative values) or pad (positive values)
            on each side of the image. Either this or the parameter `percent` may
            be set, not both at the same time.
                * If ``None``, then pixel-based cropping/padding will not be used.
                * If ``int``, then that exact number of pixels will always be cropped/padded.
                * If a ``tuple`` of two ``int`` s with values ``a`` and ``b``,
                  then each side will be cropped/padded by a random amount sampled
                  uniformly per image and side from the interval ``[a, b]``. If
                  however `sample_independently` is set to ``False``, only one
                  value will be sampled per image and used for all sides.
                * If a ``tuple`` of four entries, then the entries represent top,
                  right, bottom, left. Each entry may be a single ``int`` (always
                  crop/pad by exactly that value), a ``tuple`` of two ``int`` s
                  ``a`` and ``b`` (crop/pad by an amount within ``[a, b]``), a
                  ``list`` of ``int`` s (crop/pad by a random value that is
                  contained in the ``list``).
        percent (float or tuple):
            The number of pixels to crop (negative values) or pad (positive values)
            on each side of the image given as a *fraction* of the image
            height/width. E.g. if this is set to ``-0.1``, the transformation will
            always crop away ``10%`` of the image's height at both the top and the
            bottom (both ``10%`` each), as well as ``10%`` of the width at the
            right and left.
            Expected value range is ``(-1.0, inf)``.
            Either this or the parameter `px` may be set, not both
            at the same time.
                * If ``None``, then fraction-based cropping/padding will not be
                  used.
                * If ``float``, then that fraction will always be cropped/padded.
                * If a ``tuple`` of two ``float`` s with values ``a`` and ``b``,
                  then each side will be cropped/padded by a random fraction
                  sampled uniformly per image and side from the interval
                  ``[a, b]``. If however `sample_independently` is set to
                  ``False``, only one value will be sampled per image and used for
                  all sides.
                * If a ``tuple`` of four entries, then the entries represent top,
                  right, bottom, left. Each entry may be a single ``float``
                  (always crop/pad by exactly that percent value), a ``tuple`` of
                  two ``float`` s ``a`` and ``b`` (crop/pad by a fraction from
                  ``[a, b]``), a ``list`` of ``float`` s (crop/pad by a random
                  value that is contained in the list).
        pad_mode (int): OpenCV border mode.
        pad_cval (number, Sequence[number]):
            The constant value to use if the pad mode is ``BORDER_CONSTANT``.
                * If ``number``, then that value will be used.
                * If a ``tuple`` of two ``number`` s and at least one of them is
                  a ``float``, then a random number will be uniformly sampled per
                  image from the continuous interval ``[a, b]`` and used as the
                  value. If both ``number`` s are ``int`` s, the interval is
                  discrete.
                * If a ``list`` of ``number``, then a random value will be chosen
                  from the elements of the ``list`` and used as the value.
        pad_cval_mask (number, Sequence[number]): Same as pad_cval but only for masks.
        keep_size (bool):
            After cropping and padding, the result image will usually have a
            different height/width compared to the original input image. If this
            parameter is set to ``True``, then the cropped/padded image will be
            resized to the input image's size, i.e. the output shape is always identical to the input shape.
        sample_independently (bool):
            If ``False`` *and* the values for `px`/`percent` result in exactly
            *one* probability distribution for all image sides, only one single
            value will be sampled from that probability distribution and used for
            all sides. I.e. the crop/pad amount then is the same for all sides.
            If ``True``, four values will be sampled independently, one per side.
        interpolation (OpenCV flag): flag that is used to specify the interpolation algorithm. Should be one of:
            cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC, cv2.INTER_AREA, cv2.INTER_LANCZOS4.
            Default: cv2.INTER_LINEAR.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        any

    """

    def __init__(
        self,
        px: Optional[Union[int, List[int]]] = None,
        percent: Optional[Union[float, List[float]]] = None,
        pad_mode: int = cv2.BORDER_CONSTANT,
        pad_cval: Union[float, Sequence[float]] = 0,
        pad_cval_mask: Union[float, Sequence[float]] = 0,
        keep_size: bool = True,
        sample_independently: bool = True,
        interpolation: int = cv2.INTER_LINEAR,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(always_apply, p)

        if px is None and percent is None:
            msg = "px and percent are empty!"
            raise ValueError(msg)
        if px is not None and percent is not None:
            msg = "Only px or percent may be set!"
            raise ValueError(msg)

        self.px = px
        self.percent = percent

        self.pad_mode = pad_mode
        self.pad_cval = pad_cval
        self.pad_cval_mask = pad_cval_mask

        self.keep_size = keep_size
        self.sample_independently = sample_independently

        self.interpolation = interpolation

    def apply(
        self,
        img: np.ndarray,
        crop_params: Sequence[int] = (),
        pad_params: Sequence[int] = (),
        pad_value: float = 0,
        rows: int = 0,
        cols: int = 0,
        interpolation: int = cv2.INTER_LINEAR,
        **params: Any,
    ) -> np.ndarray:
        return F.crop_and_pad(
            img, crop_params, pad_params, pad_value, rows, cols, interpolation, self.pad_mode, self.keep_size
        )

    def apply_to_mask(
        self,
        mask: np.ndarray,
        crop_params: Optional[Sequence[int]] = None,
        pad_params: Optional[Sequence[int]] = None,
        pad_value_mask: Optional[float] = None,
        rows: int = 0,
        cols: int = 0,
        interpolation: int = cv2.INTER_NEAREST,
        **params: Any,
    ) -> np.ndarray:
        return F.crop_and_pad(
            mask, crop_params, pad_params, pad_value_mask, rows, cols, interpolation, self.pad_mode, self.keep_size
        )

    def apply_to_bbox(
        self,
        bbox: BoxInternalType,
        crop_params: Optional[Sequence[int]] = None,
        pad_params: Optional[Sequence[int]] = None,
        rows: int = 0,
        cols: int = 0,
        result_rows: int = 0,
        result_cols: int = 0,
        **params: Any,
    ) -> BoxInternalType:
        return F.crop_and_pad_bbox(bbox, crop_params, pad_params, rows, cols, result_rows, result_cols)

    def apply_to_keypoint(
        self,
        keypoint: KeypointInternalType,
        crop_params: Optional[Sequence[int]] = None,
        pad_params: Optional[Sequence[int]] = None,
        rows: int = 0,
        cols: int = 0,
        result_rows: int = 0,
        result_cols: int = 0,
        **params: Any,
    ) -> KeypointInternalType:
        return F.crop_and_pad_keypoint(
            keypoint, crop_params, pad_params, rows, cols, result_rows, result_cols, self.keep_size
        )

    @property
    def targets_as_params(self) -> List[str]:
        return ["image"]

    @staticmethod
    def __prevent_zero(val1: int, val2: int, max_val: int) -> Tuple[int, int]:
        regain = abs(max_val) + 1
        regain1 = regain // 2
        regain2 = regain // 2
        if regain1 + regain2 < regain:
            regain1 += 1

        if regain1 > val1:
            diff = regain1 - val1
            regain1 = val1
            regain2 += diff
        elif regain2 > val2:
            diff = regain2 - val2
            regain2 = val2
            regain1 += diff

        val1 = val1 - regain1
        val2 = val2 - regain2

        return val1, val2

    @staticmethod
    def _prevent_zero(crop_params: List[int], height: int, width: int) -> List[int]:
        top, right, bottom, left = crop_params

        remaining_height = height - (top + bottom)
        remaining_width = width - (left + right)

        if remaining_height < 1:
            top, bottom = CropAndPad.__prevent_zero(top, bottom, height)
        if remaining_width < 1:
            left, right = CropAndPad.__prevent_zero(left, right, width)

        return [max(top, 0), max(right, 0), max(bottom, 0), max(left, 0)]

    def get_params_dependent_on_targets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        height, width = params["image"].shape[:2]

        if self.px is not None:
            new_params = self._get_px_params()
        else:
            percent_params = self._get_percent_params()
            new_params = [
                int(percent_params[0] * height),
                int(percent_params[1] * width),
                int(percent_params[2] * height),
                int(percent_params[3] * width),
            ]

        pad_params = [max(i, 0) for i in new_params]

        crop_params = self._prevent_zero([-min(i, 0) for i in new_params], height, width)

        top, right, bottom, left = crop_params
        crop_params = [left, top, width - right, height - bottom]
        result_rows = crop_params[3] - crop_params[1]
        result_cols = crop_params[2] - crop_params[0]
        if result_cols == width and result_rows == height:
            crop_params = []

        top, right, bottom, left = pad_params
        pad_params = [top, bottom, left, right]
        if any(pad_params):
            result_rows += top + bottom
            result_cols += left + right
        else:
            pad_params = []

        return {
            "crop_params": crop_params or None,
            "pad_params": pad_params or None,
            "pad_value": None if pad_params is None else self._get_pad_value(self.pad_cval),
            "pad_value_mask": None if pad_params is None else self._get_pad_value(self.pad_cval_mask),
            "result_rows": result_rows,
            "result_cols": result_cols,
        }

    def _get_px_params(self) -> List[int]:
        if self.px is None:
            msg = "px is not set"
            raise ValueError(msg)

        if isinstance(self.px, int):
            params = [self.px] * 4
        elif len(self.px) == TWO:
            if self.sample_independently:
                params = [random.randrange(*self.px) for _ in range(4)]
            else:
                px = random.randrange(*self.px)
                params = [px] * 4
        elif isinstance(self.px[0], int):
            params = self.px
        else:
            params = [random.randrange(*i) for i in self.px]

        return params

    def _get_percent_params(self) -> List[float]:
        if self.percent is None:
            msg = "percent is not set"
            raise ValueError(msg)

        if isinstance(self.percent, float):
            params = [self.percent] * 4
        elif len(self.percent) == TWO:
            if self.sample_independently:
                params = [random.uniform(*self.percent) for _ in range(4)]
            else:
                px = random.uniform(*self.percent)
                params = [px] * 4
        elif isinstance(self.percent[0], (int, float)):
            params = self.percent
        else:
            params = [random.uniform(*i) for i in self.percent]

        return params  # params = [top, right, bottom, left]

    @staticmethod
    def _get_pad_value(pad_value: Union[float, Sequence[float]]) -> Union[int, float]:
        if isinstance(pad_value, (int, float)):
            return pad_value

        if len(pad_value) == TWO:
            a, b = pad_value
            if isinstance(a, int) and isinstance(b, int):
                return random.randint(a, b)

            return random.uniform(a, b)

        return random.choice(pad_value)

    def get_transform_init_args_names(self) -> Tuple[str, ...]:
        return (
            "px",
            "percent",
            "pad_mode",
            "pad_cval",
            "pad_cval_mask",
            "keep_size",
            "sample_independently",
            "interpolation",
        )


class RandomCropFromBorders(DualTransform):
    """Crop bbox from image randomly cut parts from borders without resize at the end

    Args:
    ----
        crop_left (float): single float value in (0.0, 1.0) range. Default 0.1. Image will be randomly cut
        from left side in range [0, crop_left * width)
        crop_right (float): single float value in (0.0, 1.0) range. Default 0.1. Image will be randomly cut
        from right side in range [(1 - crop_right) * width, width)
        crop_top (float): singlefloat value in (0.0, 1.0) range. Default 0.1. Image will be randomly cut
        from top side in range [0, crop_top * height)
        crop_bottom (float): single float value in (0.0, 1.0) range. Default 0.1. Image will be randomly cut
        from bottom side in range [(1 - crop_bottom) * height, height)
        p (float): probability of applying the transform. Default: 1.

    Targets:
        image, mask, bboxes, keypoints

    Image types:
        uint8, float32

    """

    def __init__(
        self,
        crop_left: float = 0.1,
        crop_right: float = 0.1,
        crop_top: float = 0.1,
        crop_bottom: float = 0.1,
        always_apply: bool = False,
        p: float = 1.0,
    ):
        super().__init__(always_apply, p)
        self.crop_left = crop_left
        self.crop_right = crop_right
        self.crop_top = crop_top
        self.crop_bottom = crop_bottom

    def get_params_dependent_on_targets(self, params: Dict[str, Any]) -> Dict[str, int]:
        img = params["image"]
        x_min = random.randint(0, int(self.crop_left * img.shape[1]))
        x_max = random.randint(max(x_min + 1, int((1 - self.crop_right) * img.shape[1])), img.shape[1])
        y_min = random.randint(0, int(self.crop_top * img.shape[0]))
        y_max = random.randint(max(y_min + 1, int((1 - self.crop_bottom) * img.shape[0])), img.shape[0])
        return {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max}

    def apply(
        self, img: np.ndarray, x_min: int = 0, x_max: int = 0, y_min: int = 0, y_max: int = 0, **params: Any
    ) -> np.ndarray:
        return F.clamping_crop(img, x_min, y_min, x_max, y_max)

    def apply_to_mask(
        self, mask: np.ndarray, x_min: int = 0, x_max: int = 0, y_min: int = 0, y_max: int = 0, **params: Any
    ) -> np.ndarray:
        return F.clamping_crop(mask, x_min, y_min, x_max, y_max)

    def apply_to_bbox(
        self, bbox: BoxInternalType, x_min: int = 0, x_max: int = 0, y_min: int = 0, y_max: int = 0, **params: Any
    ) -> BoxInternalType:
        rows, cols = params["rows"], params["cols"]
        return F.bbox_crop(bbox, x_min, y_min, x_max, y_max, rows, cols)

    def apply_to_keypoint(
        self,
        keypoint: KeypointInternalType,
        x_min: int = 0,
        x_max: int = 0,
        y_min: int = 0,
        y_max: int = 0,
        **params: Any,
    ) -> KeypointInternalType:
        return F.crop_keypoint_by_coords(keypoint, crop_coords=(x_min, y_min, x_max, y_max))

    @property
    def targets_as_params(self) -> List[str]:
        return ["image"]

    def get_transform_init_args_names(self) -> Tuple[str, ...]:
        return "crop_left", "crop_right", "crop_top", "crop_bottom"
