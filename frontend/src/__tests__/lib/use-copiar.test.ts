import { act, renderHook } from "@testing-library/react";
import { useCopiar } from "@/lib/use-copiar";

describe("useCopiar", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    Object.assign(navigator, { clipboard: { writeText: jest.fn().mockResolvedValue(undefined) } });
  });
  afterEach(() => jest.useRealTimers());

  it("copia o texto, vira true e volta a false depois de 2 s", async () => {
    const { result } = renderHook(() => useCopiar());
    expect(result.current[0]).toBe(false);

    await act(async () => {
      await result.current[1]("texto");
    });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("texto");
    expect(result.current[0]).toBe(true);

    act(() => {
      jest.advanceTimersByTime(2000);
    });
    expect(result.current[0]).toBe(false);
  });
});
