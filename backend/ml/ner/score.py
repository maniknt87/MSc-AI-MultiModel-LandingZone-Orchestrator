import json
import logging
import os
from pathlib import Path

from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline


logger = logging.getLogger(__name__)
recognizer = None


def init():
    global recognizer
    model_root = os.environ.get("AZUREML_MODEL_DIR")
    if not model_root:
        raise RuntimeError("AZUREML_MODEL_DIR was not supplied by Azure ML.")
    model_directory = Path(model_root)
    if not (model_directory / "config.json").is_file():
        candidates = sorted(model_directory.rglob("config.json"))
        if len(candidates) != 1:
            raise RuntimeError(
                f"Expected one cached NER model below {model_directory}; "
                f"found {len(candidates)} config.json files."
            )
        model_directory = candidates[0].parent
    logger.info("Loading cached NER model from %s", model_directory)
    tokenizer = AutoTokenizer.from_pretrained(str(model_directory), local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(
        str(model_directory), local_files_only=True
    )
    recognizer = pipeline(
        "ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple"
    )


def run(raw_data):
    try:
        data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"error": "Request must contain a non-empty 'text' field."}
        entities = recognizer(text)
        return {
            "entities": [
                {
                    "text": item["word"],
                    "label": item["entity_group"],
                    "score": float(item["score"]),
                    "start": int(item["start"]),
                    "end": int(item["end"]),
                }
                for item in entities
            ]
        }
    except Exception as exc:
        logger.exception("NER inference failed.")
        return {"error": str(exc)}
