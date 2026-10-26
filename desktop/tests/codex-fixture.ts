export function syntheticCodexEnvironment(home: string, source: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const environment: NodeJS.ProcessEnv = { HOME: home, USER: "synthetic" };
  const systemRoot = Object.entries(source).find(([name]) => name.toLowerCase() === "systemroot")?.[1];
  if (systemRoot !== undefined) environment.SystemRoot = systemRoot;
  return environment;
}
