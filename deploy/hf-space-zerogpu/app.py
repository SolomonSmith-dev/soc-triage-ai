"""Hugging Face Space entry point: Gradio SDK on ZeroGPU hardware.

The app is soc_demo.space, installed from GitHub at the commit requirements.txt pins. Cached mode reads the
harness recordings and cases copied next to this file (tests/harness/). No route requests a GPU.
"""
import os

# ZeroGPU emulates CUDA outside GPU tasks, which would move the embedding model to "cuda". Pin it to the CPU,
# where the cassettes were checked, before anything loads torch.
os.environ.setdefault("SOC_EMBED_DEVICE", "cpu")

try:  # ZeroGPU wants `spaces` imported before torch. Elsewhere it may be absent, and nothing here needs it.
    import spaces  # noqa: F401
except ImportError:
    pass

from soc_demo.space import main  # noqa: E402

if __name__ == "__main__":
    main()
