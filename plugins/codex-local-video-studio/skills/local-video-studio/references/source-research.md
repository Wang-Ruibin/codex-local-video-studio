# Source expansion for linked content

Use this procedure when the input is a social post, article, PDF, newsletter, repository page, or other source that contains outbound references. The goal is to capture the substance behind the post without following the web indefinitely.

## Build a small source graph

1. Record the supplied URL as the seed source.
2. Extract links that support the source's central claims: article cards, inline citations, project or paper links, quoted-source links, and downloads. Ignore navigation, ads, share buttons, unrelated recommendations, profile links, and comment links unless the request makes them relevant.
3. Resolve URL shorteners and tracking links to their final canonical destinations. Record both the displayed link and the resolved URL when they differ.
4. Read each materially relevant landing page. If it cites a primary source needed to verify the central claim, follow that citation too.
5. Default to two hops beyond the seed. Continue to a third hop only when it reaches the primary evidence or fills a clear factual gap. Stop when a hop is duplicate, circular, irrelevant, inaccessible after reasonable alternatives, or adds no material information.

This is relevance-bounded recursion, not a fixed quota. One authoritative linked source can be enough; a chain of mirrors is not depth.

## Social-post handling

- First try the original post and its visible card, media, quoted post, and link entities.
- If the platform blocks or truncates access, search the exact post URL, numeric post ID, author, date, and a distinctive phrase. Prefer official embed data or an indexed copy over paraphrased reposts.
- An embed endpoint may truncate long posts or omit link entities. Do not mistake a successful embed response for complete capture.
- `pic.twitter.com` and equivalent media URLs are attachments, not automatically external reference links. Inspect the media or card before classifying them.
- If an image contains the missing title or URL, inspect or OCR the image, then verify the recovered destination independently.
- Keep the original post's framing separate from the linked source's factual content. A post can be commentary, while its reference supplies the evidence.

## Source priority

Prefer sources in this order when they support the same claim:

1. Original paper, official documentation, repository, dataset, filing, or first-party announcement.
2. The canonical article or page linked by the seed source.
3. The original social post or author thread.
4. A faithful indexed copy or archive used only because the original is inaccessible.
5. Aggregators and paraphrased reposts, used as discovery aids rather than sole evidence for important claims.

For time-sensitive or consequential claims, corroborate beyond the post even when it links to a source.

## Special formats and access limits

- For PDFs, inspect the relevant text and any pages containing diagrams, tables, or claims that will appear in the video.
- For repositories, read the current README and the specific documentation or release page supporting the claim; do not infer capabilities from the repository name.
- For dynamic pages, use available rendered content, public structured data, or an official API when permitted.
- Do not bypass authentication, paywalls, robots restrictions, CAPTCHAs, or access controls. Search for an official public copy, author version, repository, abstract, or independent primary source instead.
- If essential content remains unavailable, record the gap and narrow the script. Never fill it with a plausible guess.

## Record the evidence

Structure `source.md` so another run can audit the research:

```markdown
# Source and provenance

## Seed source
- URL, author or publisher, publication date, and access result

## Followed references
- Hop 1: displayed URL -> resolved canonical URL; why it matters
- Hop 2: canonical source -> primary citation; why it matters

## Access notes
- Truncation, mirror use, unavailable media, paywall, or unresolved short link

## Claim map
- Claim used in scene 2 -> supporting source URL

## Factual digest
- Verified facts, clearly separated from interpretation

## Asset provenance
- Local asset, owner or license, and whether it may be reproduced
```

## Adaptation rule

Use the seed post as a hook or point of view when appropriate, and use the linked source for depth, evidence, examples, and caveats. The resulting video should reflect the combined source graph, not merely restate the post. Only include visuals that are user-provided, locally generated, or permitted for reuse; a readable source does not automatically grant media reuse rights.
