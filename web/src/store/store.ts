import { configureStore, createListenerMiddleware } from "@reduxjs/toolkit";
import authReducer, { logout } from "./slices/auth";
import { baseApi } from "./api/baseApi";

const logoutListener = createListenerMiddleware();
logoutListener.startListening({
  actionCreator: logout,
  effect: async (_action, listenerApi) => {
    try {
      await listenerApi.dispatch(baseApi.endpoints.logout.initiate()).unwrap();
    } catch (error) {
      console.warn("auth_logout_api_failed", error);
    }
    listenerApi.dispatch(baseApi.util.resetApiState());
  },
});

export const makeStore = () =>
  configureStore({
    reducer: {
      auth: authReducer,
      [baseApi.reducerPath]: baseApi.reducer,
    },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().prepend(logoutListener.middleware).concat(baseApi.middleware),
  });

export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore["getState"]>;
export type AppDispatch = AppStore["dispatch"];
