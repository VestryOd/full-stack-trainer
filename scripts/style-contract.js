/**
 * Single source of truth for the readability rules injected into generation prompts.
 *
 * The rules live in content/STYLE.md section 13, inside a ~~~ fenced block, so that
 * the contract the generators send to the model and the contract a human reads are
 * literally the same text. Editing STYLE.md changes every generator at once.
 */

const fs = require('fs');
const path = require('path');

const STYLE_PATH = path.join(__dirname, '..', 'content', 'STYLE.md');

/** Extract the prompt block from content/STYLE.md section 13. */
function styleContract() {
  const md = fs.readFileSync(STYLE_PATH, 'utf-8');
  const match = md.match(/\n~~~\n([\s\S]*?)\n~~~\n/);
  if (!match) {
    throw new Error(
      'content/STYLE.md: could not find the ~~~ fenced prompt block in section 13. ' +
        'Generation must not run without the readability contract.',
    );
  }
  return match[1].trim();
}

module.exports = { styleContract, STYLE_PATH };
