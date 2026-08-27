import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";

import { apiErrorMessage } from "@/utils/apiError";

function axiosError(status: number, data: unknown): AxiosError {
  const err = new AxiosError("request failed");
  err.response = {
    status,
    statusText: "",
    data,
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  };
  return err;
}

describe("apiErrorMessage", () => {
  it("prefers the backend's own explanation over the caller's fallback", () => {
    const err = axiosError(409, { detail: "Пользователь с такой почтой уже существует" });
    expect(apiErrorMessage(err, "Не удалось зарегистрироваться")).toBe(
      "Пользователь с такой почтой уже существует",
    );
  });

  it("does not render FastAPI's field-level 422 payload as a message", () => {
    const err = axiosError(422, { detail: [{ loc: ["body", "password"], msg: "too short" }] });
    expect(apiErrorMessage(err, "fallback")).toBe("Проверьте правильность заполнения полей.");
  });

  it("translates slowapi's English 429, which uses `error` rather than `detail`", () => {
    const err = axiosError(429, { error: "Rate limit exceeded: 10 per 1 hour" });
    expect(apiErrorMessage(err, "fallback")).toContain("Слишком много попыток");
  });

  it("reports a lost connection as such instead of blaming the entered data", () => {
    expect(apiErrorMessage(new AxiosError("Network Error"), "fallback")).toContain(
      "Не удалось связаться с сервером",
    );
  });

  it("does not pass a server fault off as a data problem", () => {
    expect(apiErrorMessage(axiosError(500, {}), "fallback")).toContain("Сервер временно недоступен");
  });

  it("falls back for anything that isn't an API error at all", () => {
    expect(apiErrorMessage(new Error("boom"), "fallback")).toBe("fallback");
  });
});
