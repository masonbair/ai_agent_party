import { createContext, useContext, type ReactNode } from 'react';

type DmContextValue = {
  openDmWith: (
    recipient: { kind: 'human' | 'agent'; id: string },
    displayName?: string,
  ) => void;
};

const DmContext = createContext<DmContextValue | null>(null);

export function DmProvider({
  value,
  children,
}: {
  value: DmContextValue;
  children: ReactNode;
}) {
  return <DmContext.Provider value={value}>{children}</DmContext.Provider>;
}

export function useDm(): DmContextValue | null {
  return useContext(DmContext);
}
