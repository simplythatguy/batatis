/** Run a TSX component's hooks and inspect its JSX without a browser or network. */
import { setImmediate } from "node:timers/promises";
import vm from "node:vm";
import { rolldown } from "rolldown";

const compiled = new Map();
async function compile(url) {
  if (!compiled.has(url.href)) compiled.set(url.href, (async () => {
    const bundle = await rolldown({ input: url.pathname, external: (id) => id !== url.pathname, treeshake: false });
    try { return (await bundle.generate({ format: "cjs" })).output[0].code; }
    finally { await bundle.close(); }
  })());
  return compiled.get(url.href);
}

export async function componentHarness(url, name, modules, globals = {}) {
  const slots = [];
  let cursor = 0, effects = [], dirty = false, props, tree;
  const changed = (before, after) => !before || !after || before.length !== after.length || before.some((v, i) => !Object.is(v, after[i]));
  const useMemo = (fn, deps) => {
    const i = cursor++;
    if (!slots[i] || changed(slots[i].deps, deps)) slots[i] = { value: fn(), deps };
    return slots[i].value;
  };
  const useEffect = (fn, deps) => {
    const i = cursor++;
    if (!slots[i] || changed(slots[i].deps, deps)) effects.push(() => {
      slots[i]?.cleanup?.();
      slots[i] = { deps, cleanup: fn() };
    });
  };
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!slots[i]) slots[i] = { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, (next) => {
        const value = typeof next === "function" ? next(slots[i].value) : next;
        if (!Object.is(value, slots[i].value)) { slots[i].value = value; dirty = true; }
      }];
    },
    useEffect, useLayoutEffect: useEffect, useMemo,
    useCallback: (fn, deps) => useMemo(() => fn, deps),
    useRef: (value) => useMemo(() => ({ current: value }), []),
    useId: () => useMemo(() => `test-${cursor}`, []),
    // Reads the store on every render; the test calls render() again after the store changes.
    useSyncExternalStore: (_subscribe, getSnapshot) => getSnapshot(),
    // A forwardRef component renders as a plain function component; the test passes no ref.
    forwardRef: (render) => (props) => render(props, null),
    useImperativeHandle() {},
  };
  const jsx = (type, props, key) => ({ type, props, key });
  const exports = {};
  vm.runInNewContext(await compile(url), {
    exports, module: { exports }, AbortController,
    require(id) {
      if (id === "react") return hooks;
      if (id === "react/jsx-runtime") return { jsx, jsxs: jsx, Fragment: "fragment" };
      if (id.endsWith(".css")) return {};
      // Unused imports are harmless; a used unstubbed function still fails the test.
      return modules[id] ?? {};
    },
    ...globals,
  }, { filename: url.pathname });
  function render() {
    cursor = 0; effects = []; dirty = false;
    tree = exports[name](props);
    for (const effect of effects) effect();
  }
  return {
    async render(next = props) {
      props = next;
      render();
      for (let i = 0; i < 20; i++) {
        await setImmediate();
        if (!dirty) return tree;
        render();
      }
      throw new Error(`${name} did not settle`);
    },
    unmount() { for (const slot of slots) slot?.cleanup?.(); },
    /** The module's other exports, from the same instance (its module-level state included). */
    exports,
  };
}

export function nodes(tree, predicate) {
  if (Array.isArray(tree)) return tree.flatMap((child) => nodes(child, predicate));
  if (!tree || typeof tree !== "object") return [];
  return [...(predicate(tree) ? [tree] : []), ...nodes(tree.props?.children, predicate)];
}

export function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join("");
  if (tree == null || typeof tree === "boolean") return "";
  return typeof tree === "object" ? text(tree.props?.children) : String(tree);
}
