#!/usr/bin/env python3
import os
import sys
import argparse

def install_deps():
    print("Installing video compilation dependencies...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "imageio", "imageio-ffmpeg"])
        print("Dependencies installed successfully!")
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        print("You can try running: pip install --break-system-packages imageio imageio-ffmpeg")

def sharpen_tensor(tensor, device):
    """Apply a hardware-accelerated sharpening convolution filter on the MPS/GPU device"""
    import torch
    import torch.nn.functional as F
    
    # Define a 3x3 sharpening kernel
    # [ 0, -1,  0]
    # [-1,  5, -1]
    # [ 0, -1,  0]
    kernel = torch.tensor([
        [ 0, -1,  0],
        [-1,  5, -1],
        [ 0, -1,  0]
    ], dtype=tensor.dtype, device=device)
    
    channels = tensor.shape[1]
    # Expand kernel for depthwise conv2d: (out_channels, in_channels/groups, height, width)
    kernel = kernel.view(1, 1, 3, 3).repeat(channels, 1, 1, 1)
    
    # Pad to preserve dimensions
    padded = F.pad(tensor, (1, 1, 1, 1), mode='reflect')
    
    # Run depthwise conv2d on the MPS device
    sharpened = F.conv2d(padded, kernel, groups=channels)
    return torch.clamp(sharpened, 0.0, 1.0)

def enhance_frames_quetzal_core(video_frames, target_width, target_height, device):
    """
    QuetzalCore Hardware-Accelerated 5K/HD Enhancer
    Converts frames to PyTorch tensors, moves them to MPS/GPU,
    applies neural-style sharpening, and upscales using bicubic interpolation.
    """
    import torch
    import numpy as np
    from PIL import Image
    
    print(f"🚀 QuetzalCore Enhancer: Moving frames to {device} for acceleration...")
    
    # Squeeze out leading batch dimension if 5D numpy array (e.g. (1, F, H, W, C))
    if hasattr(video_frames, 'ndim') and video_frames.ndim == 5:
        if video_frames.shape[0] == 1:
            video_frames = video_frames.squeeze(0)
        else:
            video_frames = video_frames[0]

    # Normalize input video_frames to a flat list of 3D numpy arrays or PIL Images
    frames_list = []
    
    # If video_frames is a 4D numpy array: (F, H, W, C)
    if hasattr(video_frames, 'ndim') and video_frames.ndim == 4:
        for i in range(video_frames.shape[0]):
            frames_list.append(video_frames[i])
    # If it's a list containing a single 4D array: [array(F, H, W, C)]
    elif isinstance(video_frames, list) and len(video_frames) == 1 and hasattr(video_frames[0], 'ndim') and video_frames[0].ndim == 4:
        array_4d = video_frames[0]
        for i in range(array_4d.shape[0]):
            frames_list.append(array_4d[i])
    # If it's a list containing a single list of frames: [[frame1, frame2, ...]]
    elif isinstance(video_frames, list) and len(video_frames) == 1 and isinstance(video_frames[0], list):
        frames_list = video_frames[0]
    else:
        frames_list = list(video_frames)
        
    # Convert PIL Images or numpy arrays to a single float32 tensor: (F, C, H, W)
    tensors = []
    for frame in frames_list:
        if isinstance(frame, Image.Image):
            frame_np = np.array(frame)
        else:
            frame_np = frame
        
        # Squeeze out extra batch/channel dimensions (e.g. shape (1, H, W, C) -> (H, W, C))
        if hasattr(frame_np, 'ndim'):
            while frame_np.ndim > 3:
                if frame_np.shape[0] == 1:
                    frame_np = frame_np.squeeze(0)
                else:
                    frame_np = frame_np[0]
        
        # Ensure it has shape (H, W, C)
        if frame_np.ndim == 2:
            frame_np = np.stack([frame_np]*3, axis=-1)
            
        # Convert range [0, 255] or [0.0, 1.0]
        if frame_np.dtype == np.uint8:
            frame_t = torch.from_numpy(frame_np).float() / 255.0
        else:
            frame_t = torch.from_numpy(frame_np).float()
            
        # Rearrange to (C, H, W)
        frame_t = frame_t.permute(2, 0, 1)
        tensors.append(frame_t)
        
    # Stack to (F, C, H, W)
    video_tensor = torch.stack(tensors).to(device)
    
    # Clean up NaNs from the generation model
    orig_nan_count = torch.isnan(video_tensor).sum().item()
    if orig_nan_count > 0:
        print(f"⚠️ Warning: Detected {orig_nan_count} NaNs in generated frames. Cleaning up...")
        video_tensor = torch.nan_to_num(video_tensor, nan=0.0, posinf=1.0, neginf=0.0)
    
    # Apply GPU sharpening filter
    print("🎨 Enhancing details & contrast...")
    video_tensor = sharpen_tensor(video_tensor, device)
    
    # Apply 1.1x brightness and clamping (as in QuetzalCore video_upscaler_5k.py)
    video_tensor = torch.clamp(video_tensor * 1.1, 0.0, 1.0)
    
    # Apply GPU-accelerated bicubic interpolation upscaling
    print(f"📈 Upscaling to {target_width}x{target_height} via bicubic interpolation...")
    upscaled_tensor = torch.nn.functional.interpolate(
        video_tensor,
        size=(target_height, target_width),
        mode='bicubic',
        align_corners=False
    )
    upscaled_tensor = torch.clamp(upscaled_tensor, 0.0, 1.0)
    
    # Clean up NaNs from upscaling (e.g. bicubic border edge cases on MPS)
    nan_count = torch.isnan(upscaled_tensor).sum().item()
    if nan_count > 0:
        print(f"⚠️ Warning: Detected {nan_count} NaNs in upscaled tensor. Replacing with 0.0...")
        upscaled_tensor = torch.nan_to_num(upscaled_tensor, nan=0.0, posinf=1.0, neginf=0.0)
    
    # Move back to CPU and convert back to PIL Images
    print("💾 Converting upscaled tensors back to frames...")
    upscaled_cpu = upscaled_tensor.cpu()
    enhanced_frames = []
    for i in range(upscaled_cpu.shape[0]):
        frame_t = upscaled_cpu[i].permute(1, 2, 0) # (H, W, C)
        frame_np = (frame_t.numpy() * 255.0).clip(0, 255).astype(np.uint8)
        enhanced_frames.append(Image.fromarray(frame_np))
        
    return enhanced_frames

def render_video(prompt, output_path, num_frames=16, num_steps=25, enhance=False, target_width=1024, target_height=576):
    print("Initializing local diffusion engine...")
    import torch
    try:
        from diffusers import DiffusionPipeline
    except ImportError:
        print("Error: 'diffusers' package is not installed. Please install it with: pip install diffusers transformers accelerate")
        sys.exit(1)
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")
    
    model_id = "damo-vilab/text-to-video-ms-1.7b"
    print(f"Loading model: {model_id}")
    
    try:
        # Load pipeline in float32 to prevent NaN overflows under Apple Silicon MPS
        pipe = DiffusionPipeline.from_pretrained(
            model_id, 
            torch_dtype=torch.float32
        )
        pipe = pipe.to(device)
        
        # Memory optimization for 16GB RAM Macs
        pipe.enable_attention_slicing()
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Make sure you have an active internet connection to download the weights on first run.")
        sys.exit(1)
    
    print(f"Generating video with prompt: '{prompt}'")
    print(f"Parameters: steps={num_steps}, frames={num_frames}")
    
    try:
        with torch.inference_mode():
            video_frames = pipe(prompt, num_inference_steps=num_steps, num_frames=num_frames).frames
    except Exception as e:
        print(f"Error during video generation: {e}")
        sys.exit(1)
        
    # Apply QuetzalCore Hardware-Accelerated Enhancer if selected
    if enhance:
        video_frames = enhance_frames_quetzal_core(video_frames, target_width, target_height, device)
        
    print(f"Exporting video to {output_path}...")
    
    # Check if output is mp4 or gif
    if output_path.endswith(".gif"):
        try:
            from PIL import Image
            import numpy as np
            pil_frames = []
            for frame in video_frames:
                if isinstance(frame, Image.Image):
                    pil_frames.append(frame)
                else:
                    pil_frames.append(Image.fromarray((frame * 255).astype(np.uint8)))
            
            pil_frames[0].save(
                output_path, 
                save_all=True, 
                append_images=pil_frames[1:], 
                duration=100, 
                loop=0
            )
            print(f"Successfully saved animated GIF to {output_path}")
        except Exception as e:
            print(f"Error saving GIF: {e}")
    else:
        try:
            from diffusers.utils import export_to_video
            export_to_video(video_frames, output_video_path=output_path)
            print(f"Successfully saved MP4 video to {output_path}")
        except Exception as e:
            print(f"Error exporting to MP4: {e}")
            fallback_gif = output_path.rsplit(".", 1)[0] + ".gif"
            print(f"Falling back to saving as GIF: {fallback_gif}")
            try:
                from PIL import Image
                import numpy as np
                pil_frames = []
                for frame in video_frames:
                    if isinstance(frame, Image.Image):
                        pil_frames.append(frame)
                    else:
                        pil_frames.append(Image.fromarray((frame * 255).astype(np.uint8)))
                pil_frames[0].save(
                    fallback_gif, 
                    save_all=True, 
                    append_images=pil_frames[1:], 
                    duration=100, 
                    loop=0
                )
                print(f"Saved fallback GIF successfully to {fallback_gif}")
            except Exception as ge:
                print(f"Failed to save fallback GIF: {ge}")

def main():
    parser = argparse.ArgumentParser(description="Local Diffusion Video Engine with QuetzalCore ANE/GPU Enhancement")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Install deps command
    subparsers.add_parser("install-deps", help="Install imageio and imageio-ffmpeg dependencies")
    
    # Render command
    render_parser = subparsers.add_parser("render", help="Render video from text prompt")
    render_parser.add_argument("--prompt", type=str, required=True, help="Text prompt for video generation")
    render_parser.add_argument("--output", type=str, default="output.mp4", help="Output path (.mp4 or .gif)")
    render_parser.add_argument("--frames", type=int, default=16, help="Number of frames to generate")
    render_parser.add_argument("--steps", type=int, default=25, help="Number of inference steps")
    render_parser.add_argument("--enhance", action="store_true", help="Enable QuetzalCore ANE/GPU upscaling and sharpening")
    render_parser.add_argument("--width", type=int, default=1024, help="Target width for upscaling")
    render_parser.add_argument("--height", type=int, default=576, help="Target height for upscaling")
    
    args = parser.parse_args()
    
    if args.command == "install-deps":
        install_deps()
    elif args.command == "render":
        render_video(args.prompt, args.output, args.frames, args.steps, args.enhance, args.width, args.height)

if __name__ == "__main__":
    main()
