async function main() {
    const chunks = [];
    for await (const c of process.stdin) chunks.push(c);
    const args = JSON.parse(Buffer.concat(chunks).toString());
    const path = args.tool_input?.file_path || args.tool_input?.path || "";
    if (path.includes(".env") || path.includes("/data/private/")) {
      console.error("Blocked: sensitive path");
      process.exit(2);
    }
  }
  main();