# Local, pinned Linux stack for the official openWakeWord train.py. ONNX export only.
FROM nvidia/cuda:11.7.1-cudnn8-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 OPENWAKEWORD_SOURCE=/opt/openWakeWord
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip python3.10-dev git curl ffmpeg espeak-ng \
    libespeak-ng-dev build-essential libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN python3.10 -m pip install --upgrade pip wheel "setuptools<71" \
    && python3.10 -m pip install "numpy<2" "scipy<1.14" tqdm
RUN python3.10 -m pip install torch==1.13.1+cu117 torchaudio==0.13.1+cu117 \
    --extra-index-url https://download.pytorch.org/whl/cu117
RUN python3.10 -m pip install \
    piper-phonemize espeak-phonemizer webrtcvad mutagen \
    torchinfo==1.8.0 torchmetrics==0.11.4 speechbrain==0.5.14 \
    audiomentations==0.30.0 torch-audiomentations==0.11.0 \
    acoustics==0.2.6 pronouncing deep-phonemizer==0.0.19 \
    "pyyaml>=6,<7" onnx==1.14.0 onnxruntime==1.23.2 \
    scikit-learn requests
RUN python3.10 -m pip install --no-deps piper-tts==1.3.0 pyarrow==23.0.1
RUN git clone https://github.com/dscripka/openWakeWord.git /opt/openWakeWord \
    && git -C /opt/openWakeWord checkout 368c03716d1e92591906a84949bc477f3a834455 \
    && git clone https://github.com/dscripka/piper-sample-generator.git /opt/piper-sample-generator \
    && git -C /opt/piper-sample-generator checkout f1988a4d54eddb23d99e86f0adfef6226a85acc7 \
    && sed -i 's/default="False"/default=False/g' /opt/openWakeWord/openwakeword/train.py \
    && sed -i 's/batch_size=len(X_val_fp_labels)/batch_size=2048/' /opt/openWakeWord/openwakeword/train.py \
    && python3.10 -m pip install --no-deps -e /opt/openWakeWord
RUN mkdir -p /opt/openWakeWord/openwakeword/resources/models \
    && curl -fL https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx \
       -o /opt/openWakeWord/openwakeword/resources/models/embedding_model.onnx \
    && curl -fL https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx \
       -o /opt/openWakeWord/openwakeword/resources/models/melspectrogram.onnx
WORKDIR /workspace
ENTRYPOINT ["python3.10", "pipeline.py"]

