# Product integration QC

Use this gate whenever a cut may contain an official product master, package crop, sachet, bottle, box, or product-derived overlay.

## 1. Product-necessity decision

Classify the cut before image prompting:

- `required`: the script beat is product reveal, product selection, package recognition, one-stick/one-sachet handling, mixing, consumption, proof, sold-out/repurchase/social proof, offer, stock-up, purchase limit, or CTA. These beats must show the exact designated company product.
- `optional`: the product can support the beat but is not needed to understand it. Prefer no product unless the shot is explicitly a product hero.
- `forbidden`: a strictly product-independent ingredient-only, symptom, anatomy, mechanism, or atmosphere shot remains clearer without packaging, and the sequence already has unmistakable required product shots. Do not generate or composite any product-like substitute.

Never add packaging merely to fill empty space. Never remove the designated product from a reveal/use/proof/CTA beat, and never replace it with a generic sachet, blank packet, tea bag, lookalike package, or another brand.

## 2. Required-product scene construction

Prefer `scene_native_reference_conditioned`:

- start from the approved official product master or official page asset as the image reference/edit input;
- preserve the recognizable brand, dark-green box, white stick/sachet structure, proportions, main logo placement, and product colorway;
- create the surrounding scene around that product so the product, hand, glass, table, shadow, and watercolor/photographic texture share one perspective and lighting model;
- animate this one integrated selected start image through Higgsfield; do not add a second product in post;
- accept only minor compression, fine-print softening, or brief AI shimmer when the product remains unmistakably the designated product.

Never prompt a generic, unbranded, blank, paper, or tea-like packet as a stand-in. If the scene-native edit changes the product into another package type, brand, silhouette, box/stick relationship, or colorway, reject it.

Use `official_pixel_composite` only when exact readable fine text is necessary and natural integration is feasible. In that route, generate the still and Higgsfield video without any product-shaped placeholder and reserve one clean physical placement plane with:

Generate the selected image-lane still candidate and Higgsfield video without any product-shaped placeholder. Reserve one clean physical placement plane with:

- enough empty area for the complete silhouette and its shadow;
- a camera angle compatible with the available official master;
- no hand, glass, spoon, ingredient, edge, reflection, or furniture crossing the planned silhouette unless an occlusion matte is explicitly prepared;
- stable geometry and predictable motion for tracking;
- scene lighting whose direction and softness can be reproduced on the inserted product.

Reject a plate that already contains a fake box, sachet, duplicate silhouette, dark cleanup strip, label-like texture, or object occupying the reserved zone. Never hide such an object by covering it with the official asset.

## 3. Official-pixel composite requirements

Composite the official master only when all requirements can be satisfied:

1. **Perspective:** match horizon, vanishing direction, yaw, pitch, roll, and visible side-face proportions to the placement plane. A front-facing rectangle on an angled table fails.
2. **Contact:** the product base meets a real surface. Add a scene-consistent contact shadow and, when appropriate, a soft cast shadow or reflection. Floating or clipped bases fail.
3. **Scale:** match nearby glassware, hands, ingredients, and furniture. Reject implausible product size.
4. **Occlusion:** place foreground objects and hands in front through explicit mattes. Reject any product that unnaturally covers a glass rim, hand, spoon, ingredient, table edge, or existing shadow.
5. **Lighting and color:** match exposure, white balance, contrast, saturation, shadow density, and local atmospheric softness without making official label pixels unreadable.
6. **Motion tracking:** match camera translation, scale, rotation, blur, grain, and motion cadence across the entire cut. Static pixels on a moving plate fail.
7. **Edge integrity:** inspect the full silhouette at 200 percent. Reject halos, rectangular patches, duplicated borders, dark bars, alpha seams, cut-off corners, or remnants of a generated product.
8. **Style coherence:** match the scene's watercolor, illustration, or photographic texture around non-label surfaces while preserving the official label and logo. Reject a photographic sticker on a watercolor scene or vice versa.

## 4. Required frame review

Inspect start, middle, and end frames at original resolution. Save the three frames and record booleans for:

- `exact_company_product_identity`;
- `no_generic_or_unbranded_substitute`;
- `package_structure_and_colorway_match`;
- `no_underlay_product_or_duplicate`;
- `perspective_match`;
- `surface_contact_and_shadow`;
- `scale_match`;
- `occlusion_order_correct`;
- `lighting_color_match`;
- `motion_track_match`;
- `edge_integrity`;
- `style_coherence`;
- `major_logo_label_identity_intact`;
- `minor_fine_text_softening_only`.

All values must be `true`. `minor_fine_text_softening_only` means any degradation is limited to fine print, compression, or brief edge shimmer and never changes product identity. Do not average scores. A generic substitute or wrong product is always a hard failure.

## 5. Failure response

- If the product is not required, remove product-like props and keep the cut product-free.
- If a required scene-native product changes into a generic or wrong product, quarantine it and regenerate from a simpler official-product-reference composition.
- If an official-pixel composite cannot be integrated after one approved plate attempt, switch to a simpler scene-native product hero or request a better official angle. Do not paste, cover, clone, mask over, or locally fabricate a substitute.
- Paid regeneration follows the skill's retry approval gate.
