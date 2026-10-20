import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sidebar,
  SidebarContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

export default function GalleryPage() {
  return (
    <main data-testid="gallery" className="min-h-svh bg-background text-foreground">
      <SidebarProvider>
        <Sidebar collapsible="none">
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton isActive data-testid="nav-active">
                  Intake
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton>Code</SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
        <div className="flex flex-1 flex-col gap-6 p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Button data-testid="primary-cta">Continue</Button>
            <Button variant="outline">Save draft</Button>
            <Button variant="ghost">Back</Button>
            <Badge>NBC(AE) 2023</Badge>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox data-testid="checkbox" defaultChecked aria-label="Confirmed by applicant" />
            <span className="text-sm">Confirmed by applicant</span>
          </div>
          <Input placeholder="Project address" className="max-w-sm" />
          <Textarea data-testid="textarea" defaultValue="Note" className="max-w-sm" />
          <Select>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="wood">Wood frame</SelectItem>
            </SelectContent>
          </Select>
          <Tabs defaultValue="intake">
            <TabsList>
              <TabsTrigger value="intake">Intake</TabsTrigger>
              <TabsTrigger value="code">Code</TabsTrigger>
            </TabsList>
          </Tabs>
          <Card className="max-w-sm">
            <CardHeader>
              <CardTitle>Variance</CardTitle>
            </CardHeader>
            <CardContent>Part 1, sections A-D.</CardContent>
          </Card>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">Open dialog</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Export</DialogTitle>
                <DialogDescription>Preview the variance sheet.</DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>
          <section
            className="light max-w-sm rounded-lg border border-border bg-background p-4 text-foreground"
            data-testid="pdf-sheet"
            aria-label="PDF preview"
          >
            <Button variant="outline" data-testid="pdf-outline">
              Download
            </Button>
          </section>
        </div>
      </SidebarProvider>
    </main>
  )
}
