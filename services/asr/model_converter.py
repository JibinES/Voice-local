"""
IndicWhisper Model Converter

Converts a HuggingFace IndicWhisper model to CTranslate2 INT8 format
for use with faster-whisper-server.
"""

import argparse
import os
import sys

import ctranslate2


def convert_model(model_path: str, output_dir: str, quantization: str = "int8") -> None:
    """
    Convert a HuggingFace Whisper model to CTranslate2 format.

    Args:
        model_path: Path or HuggingFace model ID (e.g., ai4bharat/indicwhisper).
        output_dir: Directory to save the converted model.
        quantization: Quantization type (default: int8).
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"Converting model: {model_path}")
    print(f"Output directory: {output_dir}")
    print(f"Quantization: {quantization}")

    converter = ctranslate2.converters.TransformersConverter(
        model_name_or_path=model_path,
    )

    converter.convert(
        output_dir=output_dir,
        quantization=quantization,
        force=True,
    )

    print(f"Model successfully converted and saved to: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert IndicWhisper HuggingFace model to CTranslate2 INT8 format."
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="HuggingFace model path or ID (e.g., ai4bharat/indicwhisper-hi).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/models/indicwhisper-ct2",
        help="Output directory for the converted model (default: /models/indicwhisper-ct2).",
    )
    parser.add_argument(
        "--quantization",
        type=str,
        default="int8",
        choices=["int8", "int8_float16", "int16", "float16", "float32"],
        help="Quantization type (default: int8).",
    )

    args = parser.parse_args()

    try:
        convert_model(args.model, args.output, args.quantization)
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
