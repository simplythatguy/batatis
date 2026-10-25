/// <reference lib="dom" />
/** The key dialog's only host access: its label, submit once, cancel. */
import { contextBridge, ipcRenderer } from "electron";

if (location.origin === "batatis-key://dialog") {
  contextBridge.exposeInMainWorld("keyDialog", {
    info: (): Promise<unknown> => ipcRenderer.invoke("key:info"),
    submit: (value: string): Promise<unknown> => ipcRenderer.invoke("key:submit", value),
    cancel: (): Promise<unknown> => ipcRenderer.invoke("key:cancel"),
  });
}
