const fs = require('fs');

// 读取App.vue文件
const content = fs.readFileSync('src/App.vue', 'utf8');

// 提取template部分
const templateMatch = content.match(/<template>([\s\S]*?)<\/template>/);
if (!templateMatch) {
  console.log('未找到template标签');
  process.exit(1);
}

const templateContent = templateMatch[1];
const lines = templateContent.split('\n');

let divStack = [];
let lineNumber = 914; // template开始的行号

lines.forEach((line, index) => {
  const actualLineNumber = lineNumber + index;
  
  // 查找开始div标签
  const openMatches = line.match(/<div[^>]*>/g);
  if (openMatches) {
    openMatches.forEach(match => {
      divStack.push({ tag: match, line: actualLineNumber });
      console.log(`第${actualLineNumber}行: 开始标签 ${match}`);
    });
  }
  
  // 查找结束div标签
  const closeMatches = line.match(/<\/div>/g);
  if (closeMatches) {
    closeMatches.forEach(() => {
      if (divStack.length > 0) {
        const openTag = divStack.pop();
        console.log(`第${actualLineNumber}行: 结束标签 </div> 匹配第${openTag.line}行的 ${openTag.tag}`);
      } else {
        console.log(`第${actualLineNumber}行: 多余的结束标签 </div>`);
      }
    });
  }
});

// 检查是否有未匹配的开始标签
if (divStack.length > 0) {
  console.log('\n未匹配的开始标签:');
  divStack.forEach(tag => {
    console.log(`第${tag.line}行: ${tag.tag}`);
  });
} else {
  console.log('\n所有div标签都已正确匹配');
}

console.log(`\n总计: ${divStack.length} 个未匹配的开始标签`);