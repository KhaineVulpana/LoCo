import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Root element not found");
}

const rawBase = import.meta.env.BASE_URL || "/";
const baseName = rawBase === "./" ? "" : rawBase.replace(/\/$/, "");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <BrowserRouter basename={baseName}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
