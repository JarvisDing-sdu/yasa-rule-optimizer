# Workflow Notes

Suggested staged workflow:

1. `stage1_generate_description`
   - input: vulnerability cases
   - output: structured descriptions
2. `stage2_generate_rule`
   - input: descriptions + rule examples
   - output: candidate rules
3. `stage3_evaluate_rule`
   - input: candidate rules + benchmark cases
   - output: FP/FN evaluation records
4. `stage4_refine_prompt`
   - input: original prompt + improvement suggestions
   - output: refined prompt for next iteration

Keep implementation scripts or notebooks here when you start automating the pipeline.
