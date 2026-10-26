/** Rail footer avatar: initials that open a small menu (Settings, Sign out). */
import { useEffect, useRef, useState } from "react";
import { useDesktop } from "../../desktop/host";
import { PeopleMenu } from "../../desktop/People";
import { initials, useAccount } from "../account";
import { Tip } from "../RelevanceRing";
import { AcIcon, usePopover } from "./bits";
import { signOut } from "./useAuthGate";

export function AccountButton() {
  const { user } = useAccount();
  const testPerson = useDesktop()?.workspace === "dev";
  const pop = usePopover();
  const [tip, setTip] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (pop.open) pop.panel.current?.querySelector<HTMLElement>("[role^=menuitem]")?.focus();
    else if (wasOpen.current && (document.activeElement === document.body || !document.activeElement)) pop.trigger.current?.focus();
    wasOpen.current = pop.open;
  }, [pop.open, pop.panel, pop.trigger]);

  if (!user) return null;
  const name = user.name || user.email;
  const close = () => pop.setOpen(false);

  function onMenuKey(e: React.KeyboardEvent) {
    const list = [...(pop.panel.current?.querySelectorAll<HTMLElement>("[role^=menuitem]") ?? [])];
    const at = list.indexOf(document.activeElement as HTMLElement);
    const to = (n: number) => { e.preventDefault(); list[(n + list.length) % list.length]?.focus(); };
    if (e.key === "ArrowDown") to(at + 1);
    else if (e.key === "ArrowUp") to(at - 1);
    else if (e.key === "Home") to(0);
    else if (e.key === "End") to(list.length - 1);
    else if (e.key === "Tab") close();
  }

  return (
    <>
      <button
        ref={pop.trigger}
        type="button"
        className="cf-avatar ac-account"
        aria-label={`Account: ${name}`}
        aria-haspopup="menu"
        aria-expanded={pop.open}
        onClick={() => { setTip(false); pop.setOpen((v) => !v); }}
        onPointerEnter={() => setTip(true)}
        onPointerLeave={() => setTip(false)}
        onFocus={() => setTip(true)}
        onBlur={() => setTip(false)}
      >
        {initials(user.name, user.email)}
      </button>
      <Tip anchor={pop.trigger.current} open={tip && !pop.open} id="rail-tip-account" side="right">
        <span>{name}</span>
      </Tip>
      {pop.open && (
        <div ref={pop.panel} className="ac-pop ac-account-menu" role="menu" aria-label="Account" style={pop.style} onKeyDown={onMenuKey}>
          <div className="ac-account-who" role="none">
            <span className="ac-account-name">{name}</span>
            {user.name && <span className="ac-account-email">{user.email}</span>}
          </div>
          <hr role="separator" />
          {testPerson && <><PeopleMenu /><hr role="separator" /></>}
          <a role="menuitem" tabIndex={-1} href="#/settings" onClick={close}>
            <AcIcon name="cog" size={16} />Settings
          </a>
          {!testPerson && (
            <button role="menuitem" tabIndex={-1} type="button" disabled={leaving} onClick={() => { setLeaving(true); void signOut(); }}>
              <AcIcon name="out" size={16} />{leaving ? "Signing out…" : "Sign out"}
            </button>
          )}
        </div>
      )}
    </>
  );
}
