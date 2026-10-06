import { compile } from "json-schema-to-typescript";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const schemasDir = path.resolve(here, "../../../packages/contracts/dist/schemas");
const out = path.resolve(here, "../src/lib/contracts.ts");

// Top-level interfaces we want to export by name from contracts.ts. Anything
// else (field-level type aliases, nested interfaces) is namespaced per-schema
// to avoid duplicate-identifier collisions across independently compiled files.
const TOP_LEVEL_NAMES = new Set([
  "AlertIngestRequest",
  "AlertIngestResponse",
  "CaseEnvelope",
  "CaseSummary",
  "CorpusVersion",
  "EvalRunSummary",
  "OverrideRequest",
  "RetrievalDebugResponse",
  "TriageJobRequest",
  "TriageJobResponse",
]);

async function main() {
  const files = (await fs.readdir(schemasDir)).filter((f) => f.endsWith(".json"));
  if (files.length === 0) {
    throw new Error(
      `No schemas in ${schemasDir}. Run 'python packages/contracts/scripts/export_schemas.py' first.`
    );
  }

  const banner = [
    "/**",
    " * Auto-generated from packages/contracts JSON Schemas.",
    " * Run `pnpm run gen:types` (or `npm run gen:types`) after Pydantic contracts change.",
    " * DO NOT EDIT BY HAND.",
    " */",
    "",
    "/* eslint-disable */",
    "",
  ].join("\n");

  // Each schema compiles independently; json-schema-to-typescript hoists
  // field-level aliases (Id, Source, CreatedAt, ...) which collide across
  // schemas when concatenated. We wrap each compile in a namespace to scope
  // the aliases, then re-export the canonical top-level interface by name.
  const blocks = [banner];
  for (const file of files.sort()) {
    const schemaName = path.basename(file, ".json");
    const raw = await fs.readFile(path.join(schemasDir, file), "utf8");
    const schema = JSON.parse(raw);
    const ts = await compile(schema, schemaName, {
      bannerComment: "",
      style: { semi: true, singleQuote: false },
      additionalProperties: false,
    });

    const nsName = `__${schemaName}NS`;
    // Inside a namespace, `export` makes the symbol visible as `NS.Symbol`.
    // We rewrite all top-level `export ` declarations to `export ` (kept) so
    // they remain reachable via the namespace alias below.
    const indented = ts
      .trim()
      .split("\n")
      .map((line) => (line ? `  ${line}` : ""))
      .join("\n");

    blocks.push(`namespace ${nsName} {\n${indented}\n}`);

    if (TOP_LEVEL_NAMES.has(schemaName)) {
      blocks.push(`export type ${schemaName} = ${nsName}.${schemaName};`);
    }
  }

  await fs.mkdir(path.dirname(out), { recursive: true });
  await fs.writeFile(out, blocks.join("\n\n") + "\n", "utf8");
  console.log(
    `wrote ${path.relative(process.cwd(), out)} (${files.length} schemas)`
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
