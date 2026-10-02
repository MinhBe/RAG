from scripts.run_seqgan_mini_generate_v3 import generate_payload, static_valid


def test_seqgan_mini_generator_truth_templates_are_static_valid():
    class Rng:
        def __init__(self, template):
            self.template = template
        def choice(self, values):
            if values and values[0] in {"eq", "neq", "lt", "gt", "between", "paren_eq"}:
                return self.template
            return 10
        def randint(self, _a, _b):
            return 3

    for template in ["eq", "neq", "lt", "gt", "between", "paren_eq"]:
        true_payload = generate_payload(Rng(template), "TRUE", [10])
        false_payload = generate_payload(Rng(template), "FALSE", [10])
        assert static_valid(true_payload)
        assert static_valid(false_payload)
        assert true_payload != false_payload
