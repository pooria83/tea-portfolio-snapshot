"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { extractApiError } from "@/lib/api";
import { toast } from "sonner";
import {
  HiOutlineUserGroup,
  HiOutlineTrash,
  HiOutlinePlus,
  HiOutlineShieldCheck,
} from "react-icons/hi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PhoneField } from "@/components/input/PhoneField";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useGetStoreMembersQuery,
  useAddStoreMemberMutation,
  useRemoveStoreMemberMutation,
} from "@/store/api/storeApi";
import type { StoreMember } from "@/types/api";

interface StoreMembersSectionProps {
  storeId: string;
  myRole: "owner" | "manager" | null;
}

export function StoreMembersSection({ storeId, myRole }: StoreMembersSectionProps) {
  const s = useTranslations("store");
  const { data: members, isLoading } = useGetStoreMembersQuery(storeId);
  const [removeMember, { isLoading: removing }] = useRemoveStoreMemberMutation();

  const isOwner = myRole === "owner";

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  const handleRemove = async (memberId: string) => {
    try {
      await removeMember({ storeId, memberId }).unwrap();
      toast.success(s("memberRemoved"));
    } catch {
      toast.error(s("memberRemoveError"));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HiOutlineUserGroup className="size-4" />
          <span className="text-sm font-medium">{s("teamMembers")}</span>
        </div>
        {isOwner && <AddMemberDialog storeId={storeId} />}
      </div>

      {members && members.length > 0 ? (
        <div className="space-y-2">
          {members.map((member) => (
            <MemberRow
              key={member.id}
              member={member}
              isOwner={isOwner}
              onRemove={handleRemove}
              removing={removing}
            />
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">{s("noStores")}</p>
      )}
    </div>
  );
}

interface MemberRowProps {
  member: StoreMember;
  isOwner: boolean;
  onRemove: (memberId: string) => void;
  removing: boolean;
}

function MemberRow({ member, isOwner, onRemove, removing }: MemberRowProps) {
  const s = useTranslations("store");
  const displayName = member.full_name || member.phone || member.email || member.user_id;

  return (
    <div className="flex items-center justify-between rounded-lg border p-3">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium">{displayName}</span>
        <span className="text-muted-foreground text-xs capitalize">{s(member.role)}</span>
        {member.email && <span className="text-muted-foreground text-xs">{member.email}</span>}
        {member.phone && (
          <span className="text-muted-foreground text-xs" dir="ltr">
            {member.phone}
          </span>
        )}
      </div>
      {isOwner && member.role !== "owner" && (
        <AlertDialog>
          <AlertDialogTrigger render={<Button variant="ghost" size="sm" />}>
            <HiOutlineTrash className="text-destructive size-4" />
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{s("removeMemberTitle")}</AlertDialogTitle>
              <AlertDialogDescription>{s("removeMemberDescription")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{s("cancelRemoveMember")}</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => onRemove(member.id)}
                disabled={removing}
                variant="destructive"
              >
                {s("confirmRemoveMember")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

interface AddMemberDialogProps {
  storeId: string;
}

function AddMemberDialog({ storeId }: AddMemberDialogProps) {
  const s = useTranslations("store");
  const [open, setOpen] = useState(false);
  const [method, setMethod] = useState<"phone" | "email">("phone");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"owner" | "manager">("manager");
  const [addMember, { isLoading: adding }] = useAddStoreMemberMutation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addMember({
        storeId,
        data: {
          ...(method === "phone" ? { phone } : { email }),
          role,
        },
      }).unwrap();
      toast.success(s("memberAdded"));
      setOpen(false);
      setPhone("");
      setEmail("");
      setRole("manager");
    } catch (err) {
      toast.error(extractApiError(err, s("memberAddError")));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        <HiOutlinePlus className="size-4" />
        {s("addMember")}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{s("addMember")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={method === "phone" ? "default" : "outline"}
              size="sm"
              onClick={() => setMethod("phone")}
            >
              {s("addMemberByPhone")}
            </Button>
            <Button
              type="button"
              variant={method === "email" ? "default" : "outline"}
              size="sm"
              onClick={() => setMethod("email")}
            >
              {s("addMemberByEmail")}
            </Button>
          </div>

          {method === "phone" ? (
            <div className="space-y-2">
              <Label>{s("memberPhone")}</Label>
              <PhoneField
                value={phone}
                onChange={setPhone}
                placeholder={s("memberPhonePlaceholder")}
              />
            </div>
          ) : (
            <div className="space-y-2">
              <Label>{s("memberEmail")}</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={s("memberEmailPlaceholder")}
                dir="ltr"
              />
            </div>
          )}

          <div className="space-y-2">
            <Label>{s("memberRole")}</Label>
            <Select
              value={role}
              onValueChange={(v: string | null) => v && setRole(v as "owner" | "manager")}
            >
              <SelectTrigger className="w-full">
                <HiOutlineShieldCheck className="size-4 shrink-0" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="manager">{s("manager")}</SelectItem>
                <SelectItem value="owner">{s("owner")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={adding || (!phone && !email)}>
              {s("addMember")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
