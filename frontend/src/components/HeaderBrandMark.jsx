import Logo from "./Logo";

export default function HeaderBrandMark({ size = 34, subtitle = "AI Shopping Copilot" }) {
  return (
    <Logo size={size} showWordmark={true} subtitle={subtitle} textColor="#ffffff" />
  );
}

