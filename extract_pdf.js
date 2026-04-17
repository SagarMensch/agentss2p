const fs = require('fs');
const pdf = require('pdf-parse');

let dataBuffer = fs.readFileSync('Agentic AI in Source-to-Pay_ Use-Case Catalogue, Controls, and a Pilot-to-Scale Roadmap.pdf');

pdf(dataBuffer).then(function(data) {
    fs.writeFileSync('pdf_extracted.txt', data.text);
    console.log("Extracted PDF text to pdf_extracted.txt, pages:", data.numpages);
}).catch(console.error);
