# High-quality science explainer method

Use this standard for science, technology, health, history, economics, and other mechanism-heavy explanations. The target is a video that earns attention and improves understanding, not a narrated slide deck.

## Narrative spine

Give every scene one role and one viewer question:

1. `hook`: show a concrete puzzle, surprising contrast, or consequence within the first few seconds. Deliver the value promised by the title rather than announcing the topic.
2. `question` or `context`: establish only the prerequisite concepts needed to follow the mechanism.
3. `mechanism`: reveal the causal chain one step at a time. Prefer a diagram or process view.
4. `evidence`: show measured data, a source-backed comparison, an experiment, or a clearly labeled illustrative relationship.
5. `implication` or `example`: connect the mechanism to something viewers recognize.
6. `recap`: compress the explanation into a memorable causal model, not a generic call to action.

Short videos can merge adjacent roles, but do not omit mechanism and evidence. Make claims proportionate to the sources and label uncertainty.

## Cognitive design

- Coherence: remove decorative facts, busy backgrounds, constant particles, and music that do not advance understanding.
- Signaling: use color, arrows, labels, spatial grouping, and timed reveals to point at the exact relationship being narrated.
- Temporal contiguity: reveal the relevant visual at the same moment as its explanation.
- Spatial contiguity: put labels next to the object or data they describe.
- Redundancy control: do not show the narration verbatim. Use a short headline and visual labels; phrase-level captions are an accessibility layer, not a second paragraph.
- Segmenting: one causal step or comparison per scene. Allow enough time to read every label before changing the visual.

## Visual planning

Choose the visual representation that answers the scene's question:

- `hero` for the opening puzzle or one central concept.
- `diagram` or `process` for causal mechanisms and sequences.
- `comparison` for before/after, alternatives, or two conditions.
- `chart` for quantitative evidence; never fabricate precision.
- `scale` or `timeline` for magnitude, distance, duration, or ordered change.
- `evidence` for source-backed findings and constraints.
- `recap` for the final causal model.

Use at least three distinct visual types in a 30-60 second explainer. Visual change should follow a new idea, not an arbitrary timer. Generated concept art can establish a scene, but diagrams and charts must carry factual explanation.

## Editorial and production pass

- Write conversational narration with concrete verbs and minimal throat-clearing.
- Keep the first scene under roughly 4.5 seconds unless the visual itself creates immediate tension.
- Prefer 5-12 scenes and 20-120 seconds for a self-contained short explainer.
- Use restrained BGM below narration; dense or sensitive passages may need almost none.
- Render a draft, inspect a contact sheet, and revise repeated layouts, clipped labels, weak visual hierarchy, and scenes whose image does not explain the spoken claim.
- Run `review_storyboard.py`; do not finalize below a score of 80 or with blocking errors.

## Research basis

- Cambridge multimedia learning principles: https://www.cambridge.org/core/books/cambridge-handbook-of-multimedia-learning/principles-for-reducing-extraneous-processing-in-multimedia-learning-coherence-signaling-redundancy-spatial-contiguity-and-temporal-contiguity-principles/C98AB3A6CE760DD63C048936EA0B3B44
- Educational video design review: https://pmc.ncbi.nlm.nih.gov/articles/PMC5132380/
- YouTube guidance on appeal, engagement, satisfaction, hooks, and retention: https://support.google.com/youtube/answer/16559650
