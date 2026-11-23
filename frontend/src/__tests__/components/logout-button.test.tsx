import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LogoutButton } from "@/components/settings/logout-button";

const push = jest.fn();
const logout = jest.fn().mockResolvedValue(undefined);
jest.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
jest.mock("@/lib/auth", () => ({ useAuth: () => ({ logout }) }));

test("sair encerra a sessão e vai para o login", async () => {
  render(<LogoutButton />);
  await userEvent.click(screen.getByRole("button", { name: /Sair da conta/ }));
  expect(logout).toHaveBeenCalled();
  await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
});
