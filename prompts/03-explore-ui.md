I want a UI to use the sprinkler detector. The user uploads a fire sprinkler plan, drags one or more reference crops on the plan to define what to look for, optionally draws a rectangle for the ROI, hits "detect", and sees the bounding boxes overlaid on the plan.

The UI calls the existing API at http://localhost:8000/detect. The class selector should populate from the API (today only "sprinkler", but the design must stay class-agnostic so adding more classes later is a config change). Match the request shape to the API's OpenAPI schema — don't invent it.

Once the UI builds and the dev server runs on http://localhost:3000, use Playwright to verify the happy path end-to-end: upload dataset/images/raw/001_Fire_Sprinkler_Plan_page_001.png, drag a crop on a sprinkler, hit detect, and verify bounding boxes render visually. Iterate on the UI code if Playwright shows the visual feedback is broken.

Output the plan as a todo list, then execute.