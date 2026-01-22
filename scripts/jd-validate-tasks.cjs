// scripts/validate-tasks.js
// Run: node scripts/validate-tasks.js
// Input: generated-tasks.json, MongoDB
// Output: validated-tasks.json

const { MongoClient } = require('mongodb');
const fs = require('fs');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'app';

// ============ Utility Functions ============

function levenshteinDistance(s1, s2) {
  const costs = [];
  for (let i = 0; i <= s1.length; i++) {
    let lastValue = i;
    for (let j = 0; j <= s2.length; j++) {
      if (i === 0) {
        costs[j] = j;
      } else if (j > 0) {
        let newValue = costs[j - 1];
        if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
        }
        costs[j - 1] = lastValue;
        lastValue = newValue;
      }
    }
    if (i > 0) costs[s2.length] = lastValue;
  }
  return costs[s2.length];
}

function similarity(s1, s2) {
  const longer = s1.length > s2.length ? s1 : s2;
  const shorter = s1.length > s2.length ? s2 : s1;
  if (longer.length === 0) return 1.0;
  const editDistance = levenshteinDistance(longer, shorter);
  return (longer.length - editDistance) / longer.length;
}

function findBestMatch(needle, haystack) {
  const needleLower = needle.toLowerCase();
  
  // Exact match
  const exact = haystack.find(h => h.toLowerCase() === needleLower);
  if (exact) return { value: exact, confidence: 1.0 };
  
  // Contains match
  const contains = haystack.find(h => 
    h.toLowerCase().includes(needleLower) || needleLower.includes(h.toLowerCase())
  );
  if (contains) return { value: contains, confidence: 0.85 };
  
  // Fuzzy match
  let bestMatch = null;
  let bestScore = 0;
  
  for (const candidate of haystack) {
    const score = similarity(needleLower, candidate.toLowerCase());
    if (score > bestScore && score > 0.6) {
      bestScore = score;
      bestMatch = candidate;
    }
  }
  
  if (bestMatch) return { value: bestMatch, confidence: bestScore };
  return null;
}

function extractMentionsFromPrompt(prompt) {
  const mentions = {
    categories: [],
    brands: [],
    maxPrice: null,
    minPrice: null,
    variants: [],
    productTypes: []
  };
  
  // Price extraction
  const maxPricePatterns = [
    /under\s*¥?\s*(\d+)/gi,
    /below\s*¥?\s*(\d+)/gi,
    /less than\s*¥?\s*(\d+)/gi,
    /(\d+)\s*yuan\s*or\s*less/gi,
    /budget.*?¥?\s*(\d+)/gi,
    /max(?:imum)?\s*¥?\s*(\d+)/gi,
    /不超过\s*(\d+)/g,
    /(\d+)\s*元以[下内]/g
  ];
  
  for (const pattern of maxPricePatterns) {
    const match = prompt.match(pattern);
    if (match) {
      const num = match[0].match(/\d+/);
      if (num) {
        mentions.maxPrice = parseInt(num[0]);
        break;
      }
    }
  }
  
  // Product type keywords (expand based on your data)
  const productKeywords = {
    'laptop': ['laptop', 'notebook', '笔记本', 'macbook'],
    'phone': ['phone', 'smartphone', 'mobile', '手机', 'iphone'],
    'headphones': ['headphones', 'earbuds', 'earphones', '耳机', 'airpods'],
    'mouse': ['mouse', '鼠标'],
    'keyboard': ['keyboard', '键盘'],
    'rice cooker': ['rice cooker', '电饭煲', '电饭锅'],
    'air fryer': ['air fryer', '空气炸锅'],
    'kettle': ['kettle', 'electric kettle', '电热水壶'],
    'shoes': ['shoes', 'sneakers', 'running shoes', '鞋', '运动鞋'],
    'monitor': ['monitor', 'display', '显示器'],
    'tablet': ['tablet', 'ipad', '平板'],
    'camera': ['camera', '相机'],
    'tv': ['tv', 'television', '电视'],
    'refrigerator': ['refrigerator', 'fridge', '冰箱'],
    'washing machine': ['washing machine', '洗衣机'],
    'vacuum': ['vacuum', '吸尘器'],
    'fan': ['fan', '风扇'],
    'air conditioner': ['air conditioner', 'ac', '空调'],
    'skincare': ['skincare', 'moisturizer', 'serum', '护肤'],
    'shampoo': ['shampoo', '洗发水'],
    'backpack': ['backpack', 'bag', '背包', '书包'],
    'watch': ['watch', 'smartwatch', '手表'],
  };
  
  const promptLower = prompt.toLowerCase();
  for (const [category, keywords] of Object.entries(productKeywords)) {
    if (keywords.some(kw => promptLower.includes(kw))) {
      mentions.productTypes.push(category);
    }
  }
  
  // Variant extraction
  const variantPatterns = [
    { pattern: /\b(black|white|silver|gold|blue|red|green|pink|gray|grey|rose gold|space gray)\b/gi, type: 'color' },
    { pattern: /\b(small|medium|large|xl|xxl|xs|s|m|l)\b/gi, type: 'size' },
    { pattern: /(\d+)\s*gb\s*ram/gi, type: 'RAM' },
    { pattern: /(\d+)\s*(gb|tb)\b/gi, type: 'storage' },
    { pattern: /(\d+)\s*(inch|")/gi, type: 'screen size' },
  ];
  
  for (const { pattern, type } of variantPatterns) {
    const matches = prompt.match(pattern);
    if (matches) {
      for (const match of matches) {
        mentions.variants.push({ type, value: match.trim().toLowerCase() });
      }
    }
  }
  
  return mentions;
}

// ============ Main Validation ============

async function validateTasks() {
  // Load generated tasks
  if (!fs.existsSync('generated-tasks.json')) {
    console.error('❌ generated-tasks.json not found. Run generate-tasks.js first.');
    process.exit(1);
  }
  
  const { tasks } = JSON.parse(fs.readFileSync('generated-tasks.json', 'utf8'));
  console.log(`Loaded ${tasks.length} tasks to validate`);
  
  const client = new MongoClient(MONGO_URI);
  
  try {
    await client.connect();
    console.log('Connected to MongoDB\n');
    
    const db = client.db(DB_NAME);
    
    // Load reference data
    const [categories, brands, priceRanges, variantData] = await Promise.all([
      db.collection('products').distinct('category'),
      db.collection('products').distinct('brand'),
      db.collection('products').aggregate([
        { $group: { _id: '$category', min: { $min: '$currentPrice' }, max: { $max: '$currentPrice' } } }
      ]).toArray(),
      db.collection('products').aggregate([
        { $unwind: '$variants' },
        { $unwind: '$variants.options' },
        { $group: { 
          _id: '$variants.label', 
          options: { $addToSet: '$variants.options.label' } 
        }}
      ]).toArray()
    ]);
    
    const priceByCategory = Object.fromEntries(priceRanges.map(p => [p._id, { min: p.min, max: p.max }]));
    const variantsByType = Object.fromEntries(variantData.map(v => [v._id.toLowerCase(), v.options.map(o => o.toLowerCase())]));
    
    console.log(`Reference data: ${categories.length} categories, ${brands.length} brands\n`);
    
    // Validate each task
    const results = [];
    
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      const validation = {
        index: i,
        prompt: task.prompt,
        verification: task.verification,
        category: task.category,
        workflow: task.workflow,
        issues: [],
        warnings: [],
        canFulfill: true
      };
      
      const mentions = extractMentionsFromPrompt(task.prompt);
      
      // Check price constraints against category ranges
      if (mentions.maxPrice && mentions.productTypes.length > 0) {
        // Try to match product types to categories
        for (const productType of mentions.productTypes) {
          const catMatch = findBestMatch(productType, categories);
          if (catMatch && priceByCategory[catMatch.value]) {
            const range = priceByCategory[catMatch.value];
            if (mentions.maxPrice < range.min) {
              validation.issues.push(
                `Price ¥${mentions.maxPrice} is below minimum for "${catMatch.value}" (min: ¥${Math.floor(range.min)})`
              );
              validation.canFulfill = false;
            }
          }
        }
      }
      
      // Check variant options exist
      for (const variant of mentions.variants) {
        const typeKey = Object.keys(variantsByType).find(t => 
          variant.type.toLowerCase().includes(t) || t.includes(variant.type.toLowerCase())
        );
        
        if (typeKey && variant.value) {
          const options = variantsByType[typeKey];
          const valueExists = options.some(o => 
            o.includes(variant.value) || variant.value.includes(o)
          );
          
          if (!valueExists) {
            validation.warnings.push(
              `Variant "${variant.value}" may not exist for ${variant.type}. Available: ${options.slice(0, 5).join(', ')}`
            );
          }
        }
      }
      
      // Try to find a matching product for complex queries
      if (mentions.productTypes.length > 0 || mentions.maxPrice) {
        const query = {};
        
        if (mentions.productTypes.length > 0) {
          const catMatches = mentions.productTypes
            .map(pt => findBestMatch(pt, categories))
            .filter(Boolean)
            .map(m => m.value);
          
          if (catMatches.length > 0) {
            query.category = { $in: catMatches };
          }
        }
        
        if (mentions.maxPrice) {
          query.currentPrice = { $lte: mentions.maxPrice };
        }
        
        if (Object.keys(query).length > 0) {
          const matchCount = await db.collection('products').countDocuments(query);
          
          if (matchCount === 0) {
            validation.issues.push(`No products match: ${JSON.stringify(query)}`);
            validation.canFulfill = false;
          } else if (matchCount < 3) {
            validation.warnings.push(`Only ${matchCount} products match constraints`);
          }
        }
      }
      
      results.push(validation);
      
      // Progress indicator
      if ((i + 1) % 10 === 0) {
        console.log(`Validated ${i + 1}/${tasks.length} tasks...`);
      }
    }
    
    // Summary
    const valid = results.filter(r => r.canFulfill && r.issues.length === 0);
    const withWarnings = results.filter(r => r.canFulfill && r.warnings.length > 0);
    const invalid = results.filter(r => !r.canFulfill);
    
    console.log(`\n${'='.repeat(50)}`);
    console.log('VALIDATION SUMMARY');
    console.log('='.repeat(50));
    console.log(`✅ Valid:         ${valid.length}`);
    console.log(`⚠️  With warnings: ${withWarnings.length}`);
    console.log(`❌ Invalid:       ${invalid.length}`);
    
    if (invalid.length > 0) {
      console.log(`\n${'─'.repeat(50)}`);
      console.log('INVALID TASKS:');
      console.log('─'.repeat(50));
      for (const r of invalid) {
        console.log(`\n[${r.index}] "${r.prompt.substring(0, 70)}..."`);
        r.issues.forEach(i => console.log(`    ❌ ${i}`));
      }
    }
    
    // Save results
    const output = {
      validatedAt: new Date().toISOString(),
      summary: {
        total: results.length,
        valid: valid.length,
        withWarnings: withWarnings.length,
        invalid: invalid.length
      },
      validTasks: valid.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        category: r.category,
        workflow: r.workflow
      })),
      invalidTasks: invalid.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        issues: r.issues
      })),
      tasksWithWarnings: withWarnings.map(r => ({
        prompt: r.prompt,
        verification: r.verification,
        warnings: r.warnings
      }))
    };
    
    fs.writeFileSync('validated-tasks.json', JSON.stringify(output, null, 2));
    console.log(`\n✅ Results saved to validated-tasks.json`);
    
  } finally {
    await client.close();
  }
}

validateTasks().catch(console.error);