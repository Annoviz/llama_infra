from scripts.router_model_compare import (
    build_model_specs,
    extract_timing_metrics,
    normalize_prompt,
    prompt_variants,
    summarize_text_results,
)


def test_build_model_specs_default_order():
    specs = build_model_specs()
    assert [spec["name"] for spec in specs] == [
        "Qwen3.6-35B",
        "Qwen3.8-27B",
        "Ternary-Bonsai-2-27B",
    ]
    assert specs[0]["prism_lm"] == 0
    assert specs[1]["prism_lm"] == 0
    assert specs[2]["prism_lm"] == 1


def test_prompt_variants_are_unique_and_include_complex_and_vision_prompts():
    prompts = prompt_variants()
    assert len(prompts) >= 2
    assert any("complex" in p.lower() for p in prompts)
    assert any("describe" in p.lower() for p in prompts)


def test_normalize_prompt_strips_whitespace_and_keeps_text():
    normalized = normalize_prompt("  long   prompt\n with  extra spaces  ")
    assert normalized == "long prompt with extra spaces"


def test_extract_timing_metrics_reports_prompt_generation_and_draft_rates():
    metrics = extract_timing_metrics(
        {
            "timings": {
                "prompt_n": 20,
                "prompt_ms": 100.0,
                "prompt_per_second": 200.0,
                "predicted_n": 40,
                "predicted_ms": 1000.0,
                "predicted_per_second": 40.0,
                "draft_n": 30,
                "draft_n_accepted": 25,
                "draft_ms": 500.0,
            }
        }
    )
    assert metrics["prompt_tokens_per_second"] == 200.0
    assert metrics["prompt_eval_tokens_per_second"] == 200.0
    assert metrics["generation_tokens_per_second"] == 40.0
    assert metrics["decode_tokens_per_second"] == 40.0
    assert metrics["draft_tokens_per_second"] == 60.0


def test_benchmark_excludes_first_text_run_from_aggregates():
    def result(elapsed_s, prompt_rate, generation_rate):
        return {
            "elapsed_s": elapsed_s,
            "timings": {
                "prompt_tokens_per_second": prompt_rate,
                "generation_tokens_per_second": generation_rate,
                "draft_tokens_per_second": None,
            },
        }

    summary = summarize_text_results(
        [result(100.0, 1000.0, 1000.0), result(4.0, 20.0, 40.0), result(6.0, 30.0, 50.0)]
    )
    assert summary["measured_text_iterations"] == 2
    assert summary["repeat_mean_elapsed_s"] == 5.0
    assert summary["repeat_mean_tokens_per_second"]["prompt_eval"] == 25.0
    assert summary["repeat_mean_tokens_per_second"]["decode"] == 45.0
