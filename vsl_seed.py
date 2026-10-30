"""VSL Seed: a seed with random/increment/decrement controls and API magic values."""
import random
from datetime import datetime

_INITIAL_STATE = random.getstate()
random.seed(datetime.now().timestamp())
_SEED_STATE = random.getstate()
random.setstate(_INITIAL_STATE)


def _new_random_seed():
    global _SEED_STATE
    prev = random.getstate()
    random.setstate(_SEED_STATE)
    seed = random.randint(1, 1125899906842624)
    _SEED_STATE = random.getstate()
    random.setstate(prev)
    return seed


class VSLSeed:
    CATEGORY = "VSL"
    DESCRIPTION = (
        "Seed in the rgthree manner: Randomize Each Time (seed -1, a fresh random "
        "seed per run), New Fixed Random, and Use Last Queued Seed. Via the API the "
        "special values -1 (random), -2 (increment), -3 (decrement) generate a "
        "server-side seed which is written back into the workflow metadata."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": -1125899906842624, "max": 1125899906842624}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("SEED",)
    FUNCTION = "main"

    @classmethod
    def IS_CHANGED(cls, seed, prompt=None, extra_pnginfo=None, unique_id=None):
        if seed in (-1, -2, -3):
            return _new_random_seed()
        return seed

    def main(self, seed=0, prompt=None, extra_pnginfo=None, unique_id=None):
        if seed in (-1, -2, -3):
            original = seed
            seed = _new_random_seed()
            print(f"[vsl_seed] server-generated random seed {seed} (was {original})")
            try:
                if unique_id is not None and isinstance(extra_pnginfo, dict):
                    for workflow in extra_pnginfo.values():
                        if not isinstance(workflow, dict):
                            continue
                        for node in workflow.get("nodes", []):
                            if str(node.get("id")) == str(unique_id):
                                for index, value in enumerate(node.get("widgets_values", [])):
                                    if value == original:
                                        node["widgets_values"][index] = seed
                if isinstance(prompt, dict) and str(unique_id) in prompt:
                    inputs = prompt[str(unique_id)].get("inputs", {})
                    if "seed" in inputs:
                        inputs["seed"] = seed
            except Exception as exc:
                print(f"[vsl_seed] metadata write-back failed: {exc}")
        return (seed,)
