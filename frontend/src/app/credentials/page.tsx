import { ComingSoon } from "@/components/ComingSoon";
import { NAV_ITEMS } from "@/lib/navigation";

export default function Page() {
  return <ComingSoon item={NAV_ITEMS.find((item) => item.href === "/credentials")!} />;
}
