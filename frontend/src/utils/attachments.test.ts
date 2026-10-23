import { describe, expect, it } from "vitest";

import { attachmentProblem } from "@/utils/attachments";

const file = (name: string, type = "", size = 10) => new File([new Uint8Array(size)], name, { type });

describe("attachmentProblem", () => {
  it("пропускает обычные документы и картинки, в том числе .zip с Windows", () => {
    for (const name of ["a.pdf", "b.DOCX", "c.xlsx", "d.pptx", "e.txt", "f.jpeg", "g.png"]) {
      expect(attachmentProblem(file(name)), name).toBeNull();
    }
    expect(attachmentProblem(file("tasks.zip", "application/x-zip-compressed"))).toBeNull();
  });

  it("пропускает скриншот из буфера без расширения", () => {
    expect(attachmentProblem(file("image", "image/png"))).toBeNull();
  });

  it("называет неподходящее расширение", () => {
    expect(attachmentProblem(file("tasks.rar"))).toContain("(.rar)");
    expect(attachmentProblem(file("README"))).toContain("Такой файл не подойдёт.");
  });

  it("отсекает файлы больше 20 МБ", () => {
    expect(attachmentProblem(file("big.pdf", "application/pdf", 20 * 1024 * 1024 + 1))).toContain("больше 20 МБ");
  });
});
