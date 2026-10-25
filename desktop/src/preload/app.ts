/// <reference lib="dom" />
/** window.batatisDesktop: the only host access a Batatis page has. Every call is checked again in main. */
import { contextBridge, ipcRenderer } from "electron";

const invoke = (channel: string, arg?: unknown): Promise<unknown> => ipcRenderer.invoke(channel, arg);

if (location.origin === "batatis://app") {
  contextBridge.exposeInMainWorld("batatisDesktop", {
    version: 1,
    info: () => invoke("batatis:info"),
    restart: () => invoke("batatis:restart"),
    switchWorkspace: (kind: string) => invoke("batatis:switch-workspace", kind),
    switchPerson: (profile: string) => invoke("batatis:switch-person", profile),
    providers: {
      list: () => invoke("batatis:providers"),
      configuration: () => invoke("batatis:ai-configuration"),
      selectGeneration: (value: string) => invoke("batatis:ai-generation", value),
      selectScreening: (value: boolean) => invoke("batatis:ai-screening", value),
      enterKey: (id: string) => invoke("batatis:key-enter", id),
      removeKey: (id: string) => invoke("batatis:key-remove", id),
      connect: (id: string) => invoke("batatis:connect", id),
      openLogin: (id: string) => invoke("batatis:open-login", id),
      cancelLogin: (id: string) => invoke("batatis:cancel-login", id),
      disconnect: (id: string) => invoke("batatis:disconnect", id),
    },
    codeDb: { choose: () => invoke("batatis:choose-codedb") },
    onChange: (listener: () => void) => {
      const handler = () => listener();
      ipcRenderer.on("batatis:changed", handler);
      return () => { ipcRenderer.removeListener("batatis:changed", handler); };
    },
  });
}
