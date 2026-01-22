// scripts/jd-generate-tasks.js
// Run: node scripts/jd-generate-tasks.js
// Input: jd-db-context.json
// Output: jd-generated-tasks.json

const Anthropic = require('@anthropic-ai/sdk');
const fs = require('fs');

const client = new Anthropic();

function formatContextForPrompt(ctx) {
  return `
## Available Data in Mock JD.com Environment

**Categories (${ctx.categories.length} total):**
${ctx.categories.join(', ')}

**Brands available:**
${ctx.brands.slice(0, 60).join(', ')}${ctx.brands.length > 60 ? ` ... and ${ctx.brands.length - 60} more` : ''}

**Price ranges by category:**
${ctx.priceRanges.map(p => `- ${p._id}: ¥${Math.floor(p.minPrice)} - ¥${Math.floor(p.maxPrice)} (${p.count} products)`).join('\n')}

**Variant types available:**
${ctx.variantTypes.map(v => `- ${v.type}: ${v.options.slice(0, 10).join(', ')}${v.options.length > 10 ? ` (+${v.options.length - 10} more)` : ''}`).join('\n')}

**Promotion types in the system:**
${ctx.promotionTypes.slice(0, 15).map(p => `- "${p.text}" (${p.count} products)`).join('\n')}

**Review tags (commonly mentioned in reviews):**
${ctx.reviewTags.slice(0, 20).map(t => `- ${t.label} (${t.count} mentions)`).join('\n')}

**Specification labels available:**
${ctx.specLabels.slice(0, 15).map(s => `- ${s.label}: e.g., ${s.sampleValues.slice(0, 3).join(', ')}`).join('\n')}

**Sample Q&A questions asked:**
${ctx.sampleQA.slice(0, 10).map(q => `- "${q.question}"`).join('\n')}

**Sample products with variants (USE THESE for tasks requiring specific variant selection):**
${ctx.productsWithVariants.map(p => {
  const variantStr = p.variants.map(v => `${v.label}: [${v.options.slice(0, 5).join(', ')}]`).join('; ');
  return `- "${p.title}" (${p.category}, ¥${p.currentPrice}, ${p.brand || 'no brand'}) — Variants: ${variantStr}`;
}).join('\n')}

**Products with active promotions:**
${ctx.productsWithPromos.map(p => `- "${p.title}" (${p.category}, ¥${p.currentPrice}) — Promos: ${p.promotions.join(', ')}`).join('\n')}

**Sample products (general):**
${ctx.sampleProducts.slice(0, 15).map(p => `- "${p.title}" (${p.category}, ¥${p.currentPrice}, rating: ${p.rating || 'N/A'}, stock: ${p.stockStatus || 'N/A'})`).join('\n')}

**Stores:**
${ctx.stores.slice(0, 15).map(s => `- ${s.name} (${s.isOfficial ? 'Official' : 'Third-party'}, ${s.rating}★) — Categories: ${(s.categories || []).join(', ')}`).join('\n')}

**Existing search history queries:**
${ctx.searchQueries.slice(0, 15).map(q => `- "${q}"`).join('\n')}

---
⚠️ CRITICAL CONSTRAINTS:
1. ONLY reference categories from the list above
2. ONLY reference brands from the list above
3. Price constraints MUST be within the ranges shown for each category
4. For tasks requiring specific variant selection (color, size, RAM, etc.), USE the sample products with variants listed above
5. Promotion text must match actual promotions in the data
6. Spec labels and review tags should match what's in the data
7. Do NOT invent products, brands, or variant options that aren't in this data
`;
}

// ============================================================
// PASTE YOUR SYSTEM PROMPT BELOW (between the backticks)
// This is the base system prompt - context will be appended
// ============================================================
const BASE_SYSTEM_PROMPT = `# Task: Generate User Prompts for JD.com Agent Evaluation

## App Capabilities

---BEGIN CAPABILITIES---
## Environment Overview

**Target Website:** JD.com

**Environment Type:** Fully mocked, programmable web application

**Key Characteristics:**

- High-value Chinese e-commerce platform
- Complex product discovery and search workflows
- Multi-step shopping cart and checkout processes
- Rich product detail pages with specifications

---

## Core Workflows

### Workflow 1: Product Discovery & Search

**User Goal:** Find specific products using search and category navigation

**Key Interactions:**

1. **Homepage Exploration**
    - 🟩 View rotating product sections (e.g., electronics, fashion, home goods)
    - 🟩 Browse category/subcategory dropdown menus
    - 🟩 Interact with promotional banners
    - 🟩 Infinite scroll through product recommendations
2. **Search Functionality**
    - 🟩 Enter search queries in the main search box
    - 🟩 View search suggestions (animated when unfocused, static when focused)
    - 🟩 Execute searches (product scope vs. store scope)
    - 🟩 View and interact with search history
    - 🟩 Navigate to search results page
3. **Search Results Navigation**
    - 🟩 Browse product listings from search results
    - 🟩 Apply filters (price range, brand, ratings, shipping options)
    - 🟩 Sort results (relevance, price, popularity, newest)
    - 🟩 View product thumbnails, prices, and ratings
    
    - 🟩 Click through to product detail pages

**Success Criteria:**

- 🟩 Agent can discover products through multiple pathways (search, categories, homepage sections)
- 🟩 Search behavior mimics realistic user patterns
- ń🟩 Filtering and sorting functions work correctly
- 🟩 Transition between pages maintains state

---

### Workflow 2: Product Evaluation & Cart Management

**User Goal:** Evaluate product details and add desired items to shopping cart

**Key Interactions:**

1. **Product Detail Page Interaction**
    - 🟩 View comprehensive product information:
        - Product images (multiple angles)
        - Pricing and promotional offers
        - Detailed specifications
        - Product descriptions
        - Customer reviews and ratings
    - 🟩 Select product variants (size, color, specifications)
    - 🟩 Adjust quantity
    - 🟩 Add to cart button interaction
2. **Shopping Cart Management**
    - 🟩 Navigate to shopping cart
    - 🟩 View cart contents with product details
    - 🟩 Modify item quantities
    - 🟩 Remove items from cart
    - 🟩 View subtotal and pricing calculations
    - 🟩 See promotional discounts applied
3. **Cross-Page Navigation**
    - 🟩 Return to homepage via logo click
    - 🟩 Continue shopping while maintaining cart state
    - 🟩 Access cart from any page

**Success Criteria:**

- 🟩 Product detail pages contain rich, realistic content
- 🟩 Cart operations (add/remove/modify) work correctly
- 🟩 Cart state persists across navigation
- 🟩 Price calculations are accurate

---

### Workflow 3: Category Navigation & Store Browsing

**User Goal:** Explore products by category and discover store-specific offerings

**Key Interactions:**

1. **Category System Navigation**
    - 🟩 Access category dropdown from homepage
    - 🟩 Browse multi-level category hierarchy
    - 🟩 Click category/subcategory to filter products
    - 🟩 View category-specific product listings
    - 🟩 Navigate between related categories
2. **Store-Scoped Search**
    - 🟩 Search within specific store scope
    - 🟩 View store search results page
    - 🟩 Browse store-specific product offerings
    - 🟩 View store information and ratings
3. **Promotional Content Interaction**
    - 🟩 View promotional banners on homepage
    - 🟩 Click promotional sections
    - 🟩 Navigate to promotional landing pages
    - 🟩 View special offers and deals
    - 🟩 Apply promotional filters

**Success Criteria:**

- 🟩 Category hierarchy is logical and complete
- 🟩 Category filtering works correctly
- 🟩 Store-scoped searches return appropriate results
- 🟩 Promotional pages are functional and realistic

---END CAPABILITIES---

## Verifiable End States
The agent's success can ONLY be verified via a final snapshot of the app. Valid verifiable states:

- **Cart contents**: Specific products are in the shopping cart with correct quantities/variants
- **Cart state**: Cart shows specific item count, subtotal, or applied promotions
- **Current screen**: User is on a specific page (product detail, search results, category listing, cart, checkout, etc.)
- **Search results**: Search results page showing results for a specific query with filters/sorting applied
- **Product selection**: Specific variant (color, size, spec) is selected on a product detail page
- **Filter/sort state**: Specific filters or sort order applied to results

**NOT verifiable (avoid prompts that rely solely on these):**
- Navigation history or pages visited during the task
- Products viewed but not added to cart
- Search history (unless currently displayed)
- Agent's internal comparisons or observations
- Transient UI states like hover menus`;

// ============================================================

// ============================================================
// PASTE YOUR USER PROMPT BELOW (between the backticks)
// ============================================================
const USER_PROMPT_TEMPLATE = `Generate 50 task prompts for a computer-use agent operating JD.com (Chinese e-commerce platform).

## Style Requirements

**Voice & Tone:**
- Sound like a real person casually asking an assistant for help with shopping
- Vary sentence structure—don't always start with \"I\"
- Use natural quantities (\"a couple\", \"a few options\") not exact numbers

**Structure:**
- Embed rich context that establishes a real shopping situation or motivation
- Include practical constraints that feel human (\"under 500 yuan\", \"needs to match my existing setup\", \"nothing too bulky\")
- Combine multiple related actions naturally (e.g., find product AND add to cart, compare options AND select one)
- Express the desired outcome as a goal, not a procedure

**Complexity:**
- Each prompt should involve 2-3 verifiable actions
- Cover different workflows: search/discovery, product evaluation, cart management, category browsing
- Vary the specificity—some prompts very targeted (specific product), others more exploratory (best option in category)

## Output Format

For each prompt, provide:
1. The natural language prompt
2. Verification criteria in parentheses with concrete, measurable outcomes

## Examples

Prompt: \"My wireless mouse just died and I need a replacement for work—something reliable and ergonomic, not a gaming mouse. Find me a good option under 200 yuan and add it to my cart.\"
Verification: (Cart contains ≥1 wireless mouse priced ≤200 yuan; product is office/ergonomic style, not gaming)

Prompt: \"Shopping for my mom's birthday and she mentioned wanting an air fryer. Find one that's well-reviewed and not too big for a small kitchen, then add it to cart so I don't forget.\"
Verification: (Cart contains ≥1 air fryer; product reviews/rating visible or product is compact/small capacity)

Prompt: \"Need to grab a few things for the new apartment—a basic rice cooker and maybe a kettle. Nothing fancy, just functional stuff for a single person. Add whatever looks good to the cart.\"
Verification: (Cart contains ≥1 rice cooker AND ≥1 electric kettle; products are basic/budget tier)

Prompt: \"I'm looking for running shoes but I'm picky about cushioning. Search for running shoes, filter to a reasonable price range, and leave me on the results so I can browse through them myself.\"
Verification: (Current screen is search results for running shoes; price filter is applied)

Prompt: \"Want to see what deals JD has on electronics right now—find the promotions section and show me what's on sale in computers or phones.\"
Verification: (Current screen shows promotional/deals page filtered to electronics/computers/phones category)

Prompt: \"Adding a laptop to my cart but I need the 16GB RAM version in silver, not the base model. Make sure you select the right specs before adding it.\"
Verification: (Cart contains ≥1 laptop; product variant shows 16GB RAM and silver color selected)

---

Now generate 50 prompts. Ensure prompts are in english (can use chinese terminology if necessary) and have variety across:
- Workflows (search/discovery, product evaluation, cart management, category/promo browsing)
- Action combinations (search+filter+view, evaluate+select variant+add to cart, browse category+add multiple items)
- Product categories (electronics, appliances, fashion, home goods, personal care, food, etc.)
- Shopping contexts (gift buying, replacing broken item, stocking up, researching before purchase, impulse buy, budget-conscious)`;
// ============================================================

// Additional instructions appended to user prompt for JSON output
const OUTPUT_FORMAT_INSTRUCTIONS = `

## Output Format

Return a JSON array where each element has:
- "prompt": the natural language task prompt
- "verification": concrete, measurable success criteria
- "category": the primary product category involved (must be from the available categories)
- "workflow": one of "search_discovery", "product_evaluation", "cart_management", "category_browsing"

Return ONLY the JSON array, no other text.`;

async function generateTasks() {
  // Load context
  if (!fs.existsSync('jd-db-context.json')) {
    console.error('❌ jd-db-context.json not found. Run jd-extract-context.js first.');
    process.exit(1);
  }
  
  const context = JSON.parse(fs.readFileSync('jd-db-context.json', 'utf8'));
  console.log('Loaded context from jd-db-context.json');
  console.log(`  - ${context.categories.length} categories`);
  console.log(`  - ${context.brands.length} brands`);
  console.log(`  - ${context.stores.length} stores`);
  console.log(`  - ${context.productsWithVariants.length} products with variants`);
  
  // Build full system prompt with context
  const systemPrompt = BASE_SYSTEM_PROMPT + '\n\n' + formatContextForPrompt(context);
  
  // Build full user prompt
  const userPrompt = USER_PROMPT_TEMPLATE + OUTPUT_FORMAT_INSTRUCTIONS;

  console.log('\nCalling Claude API...');
  
  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 12000,
    messages: [
      { role: 'user', content: userPrompt }
    ],
    system: systemPrompt
  });
  
  // Extract JSON from response
  const responseText = response.content[0].text;
  
  // Try to parse JSON (handle potential markdown code blocks)
  let tasks;
  try {
    const jsonMatch = responseText.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
      tasks = JSON.parse(jsonMatch[0]);
    } else {
      tasks = JSON.parse(responseText);
    }
  } catch (e) {
    console.error('Failed to parse response as JSON:', e);
    console.log('Raw response:', responseText);
    fs.writeFileSync('jd-raw-response.txt', responseText);
    console.log('Saved raw response to jd-raw-response.txt for debugging');
    process.exit(1);
  }
  
  // Validate tasks reference valid categories
  const validCategories = new Set(context.categories);
  tasks.forEach((t, i) => {
    if (t.category && !validCategories.has(t.category)) {
      console.warn(`⚠️  Task ${i + 1} references unknown category: "${t.category}"`);
    }
  });
  
  // Save
  const output = {
    generatedAt: new Date().toISOString(),
    contextUsed: {
      categories: context.categories.length,
      brands: context.brands.length,
      stores: context.stores.length,
      productsWithVariants: context.productsWithVariants.length
    },
    taskCount: tasks.length,
    tasks
  };
  
  fs.writeFileSync('jd-generated-tasks.json', JSON.stringify(output, null, 2));
  console.log(`\n✅ Generated ${tasks.length} tasks to jd-generated-tasks.json`);
  
  // Show summary
  const byWorkflow = {};
  const byCategory = {};
  tasks.forEach(t => {
    byWorkflow[t.workflow] = (byWorkflow[t.workflow] || 0) + 1;
    byCategory[t.category] = (byCategory[t.category] || 0) + 1;
  });
  
  console.log('\nBy workflow:');
  Object.entries(byWorkflow).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  - ${k}: ${v}`));
  
  console.log('\nBy category (top 10):');
  Object.entries(byCategory).sort((a, b) => b[1] - a[1]).slice(0, 10).forEach(([k, v]) => console.log(`  - ${k}: ${v}`));
}

generateTasks().catch(console.error);