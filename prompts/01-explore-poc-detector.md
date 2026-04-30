I want to build a detector that finds all instances of a feature in a fire sprinkler plan, given one or more reference crops. The PoC lives in a Jupyter notebook.

The detector must handle: arbitrary rotation, partial occlusion (something covering part of the symbol), lines crossing through the symbol (pipes, leaders, dimension lines), smudges and stains, scale changes, color shifts, and multiple visual formats per class (input is a list of references, not one image).

Phase 1 is sprinkler only, but the design must stay class-agnostic — adding a new class later should be a dataset-only change. Do not hardcode the class name in detection or evaluation logic.

OpenCV is a candidate. Argue for or against it, and propose alternatives if you think they fit better.