import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "../BlueBridge_TOFU_BizDev_V1.xlsx";
const outputDir = "../outputs/weekly_review_removed";
const outputPath = `${outputDir}/BlueBridge_TOFU_BizDev_V1_no_weekly_review.xlsx`;

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheetInfo = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 4000,
});
console.log("Before:");
console.log(sheetInfo.ndjson);

const weeklyReview = workbook.worksheets.getItem("Weekly Review");
weeklyReview.delete();

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 6000,
});
console.log("Formula errors:");
console.log(errors.ndjson);

const after = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 4000,
});
console.log("After:");
console.log(after.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`Saved ${outputPath}`);
