#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["opencv-python-headless", "numpy", "pillow"]
# ///
"""多帧叠加：视频或连拍里的同一块模糊文字 → 对齐后叠加，得到比任何单帧都清楚的图。

和单图 AI 超分不同：每一帧对同一笔画的采样位置略有不同，叠加用的是真实存在的额外信息（多帧超分辨率 / shift-and-add，
Farsiu et al. 2004, IEEE TIP 13(10)），所以结果可以当 read 级证据；单图超分是模型猜的笔画，不能当证据。

  frames.py stack clip.mp4 --box x0,y0,x1,y1 [--scale 3] [--every 1] [--max 60] --out text.png
  frames.py stack f1.jpg f2.jpg f3.jpg ... --box x0,y0,x1,y1 --out text.png        # 连拍、截图序列也行
  frames.py clean photo.jpg --box x0,y0,x1,y1 [--scale 3] [--h 10] --out clean.png    # 只有一张：非局部均值去噪

clean 是单张图的经典去噪（非局部均值，Buades et al. 2005, CVPR）：在图里找相似小块取平均，压掉夜景、高 ISO 的颗粒，
不像 AI 超分那样补笔画，但也不增加信息——太细的笔画会和噪点一起被抹平。所以只当“帮眼睛看”的工具：输出原图放大、
去噪两张并排，读出的字要在原图放大里也说得通才算 read；只在去噪图里“看出来”的字算 inferred。--h 越大去得越狠。
实测一张手机夜景（手机已经降噪、再经 JPEG 压缩）：h=14 把店招和“招聘”两个字整片抹掉，原图放大反而读得出。
手机照片默认 h=5 轻度试一次，没帮助就以原图放大为准；真正有用的是 RAW、老相机、监控截图这类颗粒明显的图。

- --box：要读的区域（参考帧的原图像素，留出几十像素余量方便对齐）；不给就整幅，慢且容易被运动的前景带偏。
- 参考帧自动取最清楚的一帧（拉普拉斯方差最大），其余帧用 ECC 单应性对齐到它，对齐失败的丢掉。
- 输出 <out>（中值叠加）和 <out 去扩展名>_single.png（参考帧同倍率放大），两张对照看；叠加图里才出现的笔画才算多帧带来的。
- 需要帧之间有轻微抖动；三脚架上完全不动的视频叠加只降噪、不增加分辨率。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def read_frames(srcs: list[str], every: int, limit: int) -> list[np.ndarray]:
    out = []
    if len(srcs) == 1 and Path(srcs[0]).suffix.lower() in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}:
        cap = cv2.VideoCapture(srcs[0])
        i = 0
        while len(out) < limit:
            ok, f = cap.read()
            if not ok:
                break
            if i % every == 0:
                out.append(f)
            i += 1
        cap.release()
    else:
        out = [cv2.imread(s) for s in srcs[:limit]]
        out = [f for f in out if f is not None]
    return out


def sharpness(g: np.ndarray) -> float:
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def stack(frames: list[np.ndarray], box: tuple[int, int, int, int] | None, scale: int) -> tuple[np.ndarray, np.ndarray, int]:
    if box:
        x0, y0, x1, y1 = box
        frames = [f[y0:y1, x0:x1] for f in frames]
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    ref_i = int(np.argmax([sharpness(g) for g in grays]))
    up = lambda a: cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    ref = up(grays[ref_i]).astype(np.float32)
    H, W = ref.shape
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
    warped, used = [], 0
    for f, g in zip(frames, grays):
        m = np.eye(3, dtype=np.float32)
        try:
            _, m = cv2.findTransformECC(ref, up(g).astype(np.float32), m, cv2.MOTION_HOMOGRAPHY, crit, None, 5)
        except cv2.error:
            continue
        warped.append(cv2.warpPerspective(up(f), m, (W, H), flags=cv2.INTER_CUBIC + cv2.WARP_INVERSE_MAP,
                                          borderMode=cv2.BORDER_REFLECT))
        used += 1
    med = np.median(np.stack(warped).astype(np.float32), axis=0)
    blur = cv2.GaussianBlur(med, (0, 0), 1.0 * scale / 2)
    sharp = np.clip(med + 0.6 * (med - blur), 0, 255).astype(np.uint8)   # 轻度反锐化，补偿插值的平滑
    return sharp, up(frames[ref_i]), used


def clean(img: np.ndarray, box, scale: int, h: float) -> tuple[np.ndarray, np.ndarray]:
    if box:
        x0, y0, x1, y1 = box
        img = img[y0:y1, x0:x1]
    den = cv2.fastNlMeansDenoisingColored(img, None, h, h, 7, 21)
    up = lambda a: cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return up(img), up(den)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stack")
    s.add_argument("src", nargs="+")
    s.add_argument("--box")
    s.add_argument("--scale", type=int, default=3)
    s.add_argument("--every", type=int, default=1, help="视频每隔几帧取一帧")
    s.add_argument("--max", type=int, default=60)
    s.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("clean")
    c.add_argument("image")
    c.add_argument("--box")
    c.add_argument("--scale", type=int, default=3)
    c.add_argument("--h", type=float, default=5, help="去噪强度；手机照片已降噪过，大于 8 常把细笔画一起抹掉")
    c.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "clean":
        img = cv2.imread(a.image)
        if img is None:
            sys.exit(f"读不了 {a.image}")
        box = tuple(map(int, a.box.split(","))) if a.box else None
        raw, den = clean(img, box, a.scale, a.h)
        cv2.imwrite(str(a.out), np.vstack([raw, np.full((8, raw.shape[1], 3), 255, np.uint8), den]))
        print(f"-> {a.out}（上：原图放大，下：去噪；只在下图看得出的字算 inferred）")
        return
    frames = read_frames(a.src, a.every, a.max)
    if len(frames) < 3:
        sys.exit(f"只读到 {len(frames)} 帧，至少要 3 帧")
    box = tuple(map(int, a.box.split(","))) if a.box else None
    img, single, used = stack(frames, box, a.scale)
    cv2.imwrite(str(a.out), img)
    sp = a.out.with_name(a.out.stem + "_single.png")
    cv2.imwrite(str(sp), single)
    print(f"{len(frames)} 帧读入，{used} 帧对齐成功 -> {a.out}（对照单帧 {sp}）")
    if used < len(frames) // 2:
        print("注意：一半以上的帧没对齐上，缩小 --box 只框住文字所在的平面，或换更稳的一段")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
