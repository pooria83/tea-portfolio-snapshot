"use client";

import { useState, type ReactNode } from "react";
import { Provider } from "react-redux";
import { makeStore, type AppStore } from "@/store/store";
import { AuthBootstrap } from "@/components/providers/AuthBootstrap";

type Props = {
  children: ReactNode;
};

export function ReduxProvider({ children }: Props) {
  const [store] = useState<AppStore>(makeStore);

  return (
    <Provider store={store}>
      <AuthBootstrap />
      {children}
    </Provider>
  );
}
