# ----------------------------------------------
# PowerShell script to install AMD ROCm PyTorch
# For Python 3.12 on Windows
# ----------------------------------------------

# Make sure the conda environment is activated before running this script

Write-Host "Installing ROCm SDK core, devel, libraries..." -ForegroundColor Cyan

pip install --no-cache-dir `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/rocm_sdk_core-0.1.dev0-py3-none-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/rocm_sdk_devel-0.1.dev0-py3-none-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/rocm_sdk_libraries_custom-0.1.dev0-py3-none-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/rocm-0.1.dev0.tar.gz

Write-Host "Installing ROCm PyTorch, torchaudio, and torchvision..." -ForegroundColor Cyan

pip install --no-cache-dir `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/torch-2.9.0+rocmsdk20251116-cp312-cp312-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/torchaudio-2.9.0+rocmsdk20251116-cp312-cp312-win_amd64.whl `
    https://repo.radeon.com/rocm/windows/rocm-rel-7.1.1/torchvision-0.24.0+rocmsdk20251116-cp312-cp312-win_amd64.whl 

Write-Host "ROCm PyTorch installation completed." -ForegroundColor Green

Write-Host "Installing whisperx, faster-whisper, ctranslate2, onnxruntime, onxruntime-tools, soundfile, ffmpeg-python, numpy, tqdm, pydub, huggingface_hub" -ForegroundColor Cyan

pip install whisperx --no-deps 
pip install faster-whisper ctranslate2 onnxruntime onnxruntime-tools `
            soundfile ffmpeg-python numpy tqdm pydub huggingface_hub `
            transformers==4.48.0 nltk>=3.9.1 pandas==2.2.3

Write-Host "whisperx installation completed." -ForegroundColor Green