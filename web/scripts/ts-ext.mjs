/** Resolve extensionless relative imports to `.ts` so node --test can load the web sources. */
export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith(".") && !/\.(tsx?|jsx?|json|css)$/.test(specifier)) {
    return nextResolve(`${specifier}.ts`, context);
  }
  return nextResolve(specifier, context);
}
